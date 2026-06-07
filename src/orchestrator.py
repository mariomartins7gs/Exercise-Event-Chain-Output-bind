from datetime import timedelta

from src.models import OrderStatus


async def order_workflow(context) -> dict:
    order = context.get_input()

    validated = await context.call_activity("validate_order", order)

    counter = await context.call_activity("get_next_counter", {})
    validated.update(counter)

    await context.call_activity(
        "write_status_update",
        {
            "orderId": validated.get("instanceId"),
            "status": OrderStatus.VALIDATING.value,
            "details": "Order validation complete",
        },
    )

    await context.call_activity(
        "send_sms",
        {
            "phoneNumber": validated.get("customerPhone"),
            "message": f"Order {validated.get('displayOrder')} received. Confirm at: /api/confirm_handler",
            "orderId": validated.get("instanceId"),
        },
    )

    await context.call_activity(
        "write_status_update",
        {
            "orderId": validated.get("instanceId"),
            "status": OrderStatus.SMS_SENT.value,
            "details": "SMS sent via ACS",
        },
    )

    expiry = context.current_utc_datetime + timedelta(seconds=180)
    await context.call_activity(
        "write_status_update",
        {
            "orderId": validated.get("instanceId"),
            "status": OrderStatus.PENDING_CONFIRMATION.value,
            "details": f"Waiting for confirmation (expires at {expiry.isoformat()})",
        },
    )

    timer_task = context.create_timer(expiry)
    event_task = context.wait_for_external_event("Confirmed")
    winner = await context.task_any([timer_task, event_task])

    if winner == timer_task:
        await context.call_activity(
            "write_status_update",
            {
                "orderId": validated.get("instanceId"),
                "status": OrderStatus.EXPIRED.value,
                "details": "Confirmation timeout",
            },
        )
        await context.call_activity(
            "log_expired_order",
            {
                "orderId": validated.get("instanceId"),
                "displayOrder": validated.get("displayOrder"),
                "customerName": validated.get("customerName"),
                "customerPhone": validated.get("customerPhone"),
                "total": validated.get("total", 0),
                "expiresAt": expiry.isoformat(),
                "PartitionKey": "ExpiredOrder",
                "RowKey": validated.get("instanceId"),
            },
        )
        return {**counter, "status": OrderStatus.EXPIRED.value}
    else:
        confirmed = await context.call_activity("process_order", validated)
        await context.call_activity(
            "write_status_update",
            {
                "orderId": validated.get("instanceId"),
                "status": OrderStatus.CONFIRMED.value,
                "details": "Confirmed by user",
            },
        )
        await context.call_activity("write_to_cosmos", confirmed)
        return {**counter, "status": OrderStatus.COMPLETED.value}
