import os
from datetime import datetime, timezone

from src.counter import OrderCounter
from src.models import OrderPayload, OrderStatus


async def validate_order(order_data: dict) -> dict:
    try:
        payload = OrderPayload(**order_data)
        return {
            **payload.model_dump(),
            "status": OrderStatus.VALIDATING.value,
        }
    except Exception as e:
        raise ValueError(f"Invalid order: {e}")


async def get_next_counter(container) -> dict:
    counter = OrderCounter(container)
    return await counter.get_next_id()


async def send_sms(payload: dict, acs_client) -> dict:
    provider = os.environ.get("SMS_PROVIDER", "acs").lower()
    if provider == "simulated":
        return {
            "messageId": "simulated-msg-id",
            "status": "sent",
            "provider": "simulated",
        }
    try:
        result = await acs_client.send(
            from_=os.environ.get("ACS_PHONE_NUMBER", ""),
            to=[payload["phoneNumber"]],
            message=payload["message"],
        )
        return {
            "messageId": result[0].message_id if result else "unknown",
            "status": "sent",
        }
    except Exception:
        return {"messageId": "", "status": "failed", "provider": "acs"}


async def write_status_update(payload: dict, cosmos_container) -> dict:
    order_id = payload["orderId"]
    status = payload["status"]
    details = payload.get("details", "")
    now = datetime.now(timezone.utc).isoformat()
    entry = {"status": status, "timestamp": now, "details": details}
    try:
        doc = await cosmos_container.read_item(item=order_id, partition_key=order_id)
        doc["status"] = status
        doc["lastUpdatedAt"] = now
        doc.setdefault("timeline", []).append(entry)
        result = await cosmos_container.replace_item(item=doc, body=doc)
        return result
    except Exception:
        doc = {
            "id": order_id,
            "orderId": order_id,
            "status": status,
            "lastUpdatedAt": now,
            "timeline": [entry],
        }
        result = await cosmos_container.create_item(body=doc)
        return result


async def process_order(order_data: dict) -> dict:
    return {
        **order_data,
        "status": OrderStatus.PROCESSING.value,
        "processedAt": datetime.now(timezone.utc).isoformat(),
    }


async def write_to_cosmos(order_document: dict, cosmos_container) -> dict:
    result = await cosmos_container.upsert_item(body=order_document)
    return result


async def log_expired_order(expired_order: dict, table_client) -> dict:
    result = await table_client.create_entity(entity=expired_order)
    return result
