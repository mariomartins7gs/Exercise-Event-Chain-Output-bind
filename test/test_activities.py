import pytest

from src.activities import (
    get_next_counter,
    log_expired_order,
    process_order,
    send_sms,
    validate_order,
    write_status_update,
    write_to_cosmos,
)
from src.models import OrderStatus


class TestValidateOrder:
    async def test_validate_order_valid(self, sample_order):
        result = await validate_order(sample_order)
        assert result["customerName"] == "Maria Silva"
        assert result["status"] == OrderStatus.VALIDATING.value

    async def test_validate_order_invalid(self):
        with pytest.raises(ValueError, match="Invalid order"):
            await validate_order({"customerName": ""})


class TestGetNextCounter:
    async def test_get_next_counter_success(self, mock_cosmos_container):
        mock_cosmos_container.read_item.return_value = {
            "id": "orderCounter",
            "currentValue": 42,
            "_etag": '"etag-1"',
        }
        mock_cosmos_container.replace_item.return_value = {
            "id": "orderCounter",
            "currentValue": 43,
            "_etag": '"etag-2"',
        }

        result = await get_next_counter(mock_cosmos_container)
        assert result["displayId"] == 43

    async def test_get_next_counter_failure(self, mock_cosmos_container):
        mock_cosmos_container.read_item.side_effect = Exception("Cosmos DB down")

        with pytest.raises(Exception, match="Cosmos DB down"):
            await get_next_counter(mock_cosmos_container)


class TestSendSms:
    async def test_send_sms_valid(self, mock_acs_client):
        result = await send_sms(
            {
                "phoneNumber": "+351911234567",
                "message": "Test",
                "orderId": "ORD-0042",
            },
            mock_acs_client,
        )
        assert result["status"] == "sent"

    async def test_send_sms_simulated(self, mocker):
        mocker.patch.dict("os.environ", {"SMS_PROVIDER": "simulated"})
        result = await send_sms(
            {
                "phoneNumber": "+351911234567",
                "message": "Test",
                "orderId": "ORD-0042",
            },
            None,
        )
        assert result["status"] == "sent"
        assert result["provider"] == "simulated"

    async def test_send_sms_acs_failure(self, mock_acs_client):
        mock_acs_client.send.side_effect = Exception("ACS error")

        result = await send_sms(
            {
                "phoneNumber": "+351911234567",
                "message": "Test",
                "orderId": "ORD-0042",
            },
            mock_acs_client,
        )
        assert result["status"] == "failed"


class TestWriteStatusUpdate:
    async def test_write_status_update_new(self, mock_cosmos_container):
        mock_cosmos_container.read_item.side_effect = Exception("Not found")
        mock_cosmos_container.create_item.return_value = {"id": "ORD-0042"}

        result = await write_status_update(
            {
                "orderId": "ORD-0042",
                "status": OrderStatus.VALIDATING.value,
                "details": "Validation complete",
            },
            mock_cosmos_container,
        )
        assert result["id"] == "ORD-0042"

    async def test_write_status_update_append(self, mock_cosmos_container, valid_order_status):
        mock_cosmos_container.read_item.return_value = valid_order_status
        mock_cosmos_container.replace_item.return_value = valid_order_status

        result = await write_status_update(
            {
                "orderId": "ORD-0042-a1b2c3d4",
                "status": OrderStatus.CONFIRMED.value,
                "details": "Confirmed by user",
            },
            mock_cosmos_container,
        )
        assert "timeline" in result


class TestProcessOrder:
    async def test_process_order(self, sample_order):
        result = await process_order(
            {**sample_order, "displayOrder": "ORD-0042", "displayId": 42}
        )
        assert result["status"] == OrderStatus.PROCESSING.value
        assert "processedAt" in result


class TestWriteToCosmos:
    async def test_write_to_cosmos(self, mock_cosmos_container, sample_order):
        mock_cosmos_container.upsert_item.return_value = {"id": "ORD-0042"}

        result = await write_to_cosmos(
            {**sample_order, "id": "ORD-0042", "status": OrderStatus.COMPLETED.value},
            mock_cosmos_container,
        )
        assert result["id"] == "ORD-0042"


class TestLogExpiredOrder:
    async def test_log_expired_order(self, mock_table_service_client, expired_order_entry):
        mock_table_service_client.create_entity.return_value = expired_order_entry

        result = await log_expired_order(
            expired_order_entry, mock_table_service_client
        )
        assert result["PartitionKey"] == "ExpiredOrder"
