import json
import os

import azure.functions as func
from azure.cosmos.aio import ContainerClient as CosmosContainerClient
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient

from src.counter import CounterConflictError, OrderCounter
from src.models import OrderPayload

app = func.FunctionApp()


def _get_cosmos_container(container_name: str) -> CosmosContainerClient:
    endpoint = os.environ["COSMOS_DB_ACCOUNT_ENDPOINT"]
    database = os.environ["COSMOS_DB_DATABASE_NAME"]
    credential = DefaultAzureCredential()
    return CosmosContainerClient(
        endpoint,
        credential,
        database_name=database,
        container_name=container_name,
    )


def _get_blob_service_client() -> BlobServiceClient:
    account_url = os.environ["AzureWebJobsStorage__blobServiceUri"]
    credential = DefaultAzureCredential()
    return BlobServiceClient(account_url, credential)


@app.route(route="submit_order", auth_level=func.AuthLevel.ANONYMOUS)
@app.durable_client_input(client_name="df_client")
async def submit_order(req: func.HttpRequest, df_client) -> func.HttpResponse:
    try:
        body = req.get_json()
    except (ValueError, TypeError):
        return func.HttpResponse("Invalid JSON body", status_code=400)

    if not body:
        return func.HttpResponse("Empty request body", status_code=400)

    try:
        OrderPayload(**body)
    except Exception:
        return func.HttpResponse("Invalid order payload", status_code=400)

    cosmos_client = _get_cosmos_container("Orders")
    async with cosmos_client:
        try:
            counter = OrderCounter(cosmos_client)
            counter_result = await counter.get_next_id()
        except CounterConflictError:
            return func.HttpResponse(
                "Counter exhausted, try again", status_code=503
            )
        except Exception:
            return func.HttpResponse(
                "Counter service unavailable", status_code=503
            )

        blob_name = f"{counter_result['displayOrder']}.json"
        try:
            blob_svc = _get_blob_service_client()
            async with blob_svc:
                blob_container = blob_svc.get_container_client("orders-inbox")
                await blob_container.upload_blob(
                    name=blob_name,
                    data=json.dumps(body).encode("utf-8"),
                    overwrite=False,
                )
        except Exception:
            return func.HttpResponse(
                "Failed to write order blob", status_code=500
            )

    try:
        await df_client.start_new_orchestration(
            function_name="order_workflow",
            instance_id=counter_result["instanceId"],
            input=body,
        )
    except Exception:
        pass

    return func.HttpResponse(
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


@app.route(route="confirm_handler", auth_level=func.AuthLevel.ANONYMOUS)
@app.durable_client_input(client_name="df_client")
async def confirm_handler(
    req: func.HttpRequest, df_client
) -> func.HttpResponse:
    try:
        body = req.get_json()
        instance_id = body.get("instance_id")
    except (ValueError, TypeError):
        instance_id = None

    if not instance_id:
        return func.HttpResponse("Missing instance_id", status_code=400)

    try:
        status = await df_client.get_status(instance_id)
    except Exception:
        return func.HttpResponse("Orchestration not found", status_code=404)

    if not status or not status.status:
        return func.HttpResponse("Orchestration not found", status_code=404)

    if status.status != "Running":
        return func.HttpResponse(
            f"Orchestration already completed with status: {status.status}",
            status_code=410,
        )

    await df_client.raise_event(
        instance_id=instance_id, event_name="Confirmed", data={}
    )
    return func.HttpResponse("Order confirmed", status_code=200)


@app.route(route="get_order_status", auth_level=func.AuthLevel.ANONYMOUS)
async def get_order_status(req: func.HttpRequest) -> func.HttpResponse:
    order_id = req.params.get("orderId")
    if not order_id:
        return func.HttpResponse("Missing orderId parameter", status_code=400)

    cosmos_client = _get_cosmos_container("Orders")
    async with cosmos_client:
        try:
            doc = await cosmos_client.read_item(
                item=order_id, partition_key=order_id
            )
        except Exception:
            return func.HttpResponse("Order not found", status_code=404)

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

    return func.HttpResponse(
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


@app.event_grid_trigger(arg_name="event")
@app.durable_client_input(client_name="df_client")
async def order_validator(event: func.EventGridEvent, df_client):
    await df_client.start_new_orchestration(
        function_name="order_workflow",
        instance_id=None,
        input=event.get_json(),
    )
    return {"status": "started"}
