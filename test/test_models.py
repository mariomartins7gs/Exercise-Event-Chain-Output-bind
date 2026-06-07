import pytest
from pydantic import ValidationError

from src.models import (
    CounterDocument,
    FinalOrder,
    OrderItem,
    OrderPayload,
    OrderStatus,
    OrderStatusResponse,
    SmsRequest,
    SmsResult,
    StatusUpdate,
)


class TestOrderPayload:
    def test_valid_order_payload(self, sample_order):
        payload = OrderPayload(**sample_order)
        assert payload.customerName == "Maria Silva"
        assert len(payload.items) == 2
        assert payload.total == 61.00

    def test_order_missing_items(self, sample_order):
        data = {k: v for k, v in sample_order.items() if k != "items"}
        with pytest.raises(ValidationError):
            OrderPayload(**data)

    def test_order_empty_items(self, sample_order):
        data = {**sample_order, "items": []}
        with pytest.raises(ValidationError):
            OrderPayload(**data)

    def test_order_negative_total(self, sample_order):
        data = {**sample_order, "total": -5.00}
        with pytest.raises(ValidationError):
            OrderPayload(**data)

    def test_order_invalid_phone(self, sample_order):
        data = {**sample_order, "customerPhone": "abc"}
        with pytest.raises(ValidationError):
            OrderPayload(**data)

    def test_order_name_too_long(self, sample_order):
        data = {**sample_order, "customerName": "A" * 101}
        with pytest.raises(ValidationError):
            OrderPayload(**data)


class TestSmsRequest:
    def test_sms_request_valid(self):
        req = SmsRequest(phoneNumber="+351911234567", message="Your order", orderId="ORD-0042")
        assert req.phoneNumber == "+351911234567"


class TestCounterDocument:
    def test_counter_document_valid(self):
        doc = CounterDocument(id="orderCounter", currentValue=42)
        assert doc.currentValue == 42
        assert doc.id == "orderCounter"


class TestStatusUpdate:
    def test_status_update_valid(self):
        from datetime import datetime, timezone

        update = StatusUpdate(
            orderId="ORD-0042",
            status=OrderStatus.PENDING_CONFIRMATION,
            timestamp=datetime.now(timezone.utc),
        )
        assert update.status == OrderStatus.PENDING_CONFIRMATION

    def test_order_status_response(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        update = StatusUpdate(
            orderId="ORD-0042", status=OrderStatus.SUBMITTED, timestamp=now
        )
        response = OrderStatusResponse(
            orderId="ORD-0042",
            displayId=42,
            displayOrder="ORD-0042",
            status=OrderStatus.PENDING_CONFIRMATION,
            timeline=[update],
            expiresAt=None,
            secondsRemaining=137,
        )
        assert response.status == OrderStatus.PENDING_CONFIRMATION
        assert response.secondsRemaining == 137
