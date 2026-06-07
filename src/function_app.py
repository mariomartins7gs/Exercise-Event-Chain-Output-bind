import json

from azure.functions import HttpResponse

from src.counter import CounterConflictError, OrderCounter
from src.models import OrderPayload


async def submit_order(
    req, cosmos_container, blob_client, df_client
) -> HttpResponse:
    try:
        body = req.get_json()
    except (ValueError, TypeError):
        return HttpResponse("Invalid JSON body", status_code=400)

    if not body:
        return HttpResponse("Empty request body", status_code=400)

    try:
        OrderPayload(**body)
    except Exception:
        return HttpResponse("Invalid order payload", status_code=400)

    try:
        counter = OrderCounter(cosmos_container)
        counter_result = await counter.get_next_id()
    except CounterConflictError:
        return HttpResponse("Counter exhausted, try again", status_code=503)
    except Exception:
        return HttpResponse("Counter service unavailable", status_code=503)

    blob_name = f"{counter_result['displayOrder']}.json"
    try:
        await blob_client.upload_blob(
            name=f"orders-inbox/{blob_name}",
            data=json.dumps(body).encode("utf-8"),
            overwrite=False,
        )
    except Exception:
        return HttpResponse("Failed to write order blob", status_code=500)

    try:
        await df_client.start_new_orchestration(
            function_name="order_workflow",
            instance_id=counter_result["instanceId"],
            input=body,
        )
    except Exception:
        pass

    return HttpResponse(
        json.dumps(
            {
                "orderId": counter_result["instanceId"],
                "displayId": counter_result["displayId"],
                "displayOrder": counter_result["displayOrder"],
                "status": "submitted",
            }
        ),
        status_code=202,
        mimetype="application/json",
    )


async def confirm_handler(req, df_client) -> HttpResponse:
    try:
        body = req.get_json()
        instance_id = body.get("instance_id")
    except (ValueError, TypeError):
        instance_id = None

    if not instance_id:
        return HttpResponse("Missing instance_id", status_code=400)

    try:
        status = await df_client.get_status(instance_id)
    except Exception:
        return HttpResponse("Orchestration not found", status_code=404)

    if not status or not status.status:
        return HttpResponse("Orchestration not found", status_code=404)

    if status.status != "Running":
        return HttpResponse(
            f"Orchestration already completed with status: {status.status}",
            status_code=410,
        )

    await df_client.raise_event(
        instance_id=instance_id, event_name="Confirmed", data={}
    )
    return HttpResponse("Order confirmed", status_code=200)


async def get_order_status(req, cosmos_container) -> HttpResponse:
    order_id = req.params.get("orderId")
    if not order_id:
        return HttpResponse("Missing orderId parameter", status_code=400)

    try:
        doc = await cosmos_container.read_item(
            item=order_id, partition_key=order_id
        )
    except Exception:
        return HttpResponse("Order not found", status_code=404)

    seconds_remaining = None
    if doc.get("status") == "pending_confirmation" and doc.get("expiresAt"):
        try:
            from datetime import datetime, timezone

            expires = datetime.fromisoformat(
                doc["expiresAt"].replace("Z", "+00:00")
            )
            now = datetime.now(timezone.utc)
            seconds_remaining = max(0, int((expires - now).total_seconds()))
        except Exception:
            seconds_remaining = None

    return HttpResponse(
        json.dumps(
            {
                "orderId": doc.get("orderId"),
                "displayId": doc.get("displayId"),
                "displayOrder": doc.get("displayOrder"),
                "status": doc.get("status"),
                "secondsRemaining": seconds_remaining,
                "expiresAt": doc.get("expiresAt"),
                "lastUpdatedAt": doc.get("lastUpdatedAt"),
                "timeline": doc.get("timeline", []),
            }
        ),
        status_code=200,
        mimetype="application/json",
    )


async def order_validator(event, df_client):
    await df_client.start_new_orchestration(
        function_name="order_workflow",
        instance_id=None,
        input=event.get("data", {}),
    )
    return {"status": "started"}
