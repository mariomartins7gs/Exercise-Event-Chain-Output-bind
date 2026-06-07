import pytest
from azure.cosmos import exceptions

from src.counter import CounterConflictError, OrderCounter


class TestOrderCounter:
    async def test_counter_read_increment(self, mock_cosmos_container):
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

        counter = OrderCounter(mock_cosmos_container)
        result = await counter.get_next_id()

        assert result["displayId"] == 43
        assert result["displayOrder"] == "ORD-0043"
        assert result["instanceId"].startswith("ORD-0043-")

    async def test_counter_increment_with_etag(self, mock_cosmos_container):
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

        counter = OrderCounter(mock_cosmos_container)
        await counter.get_next_id()

        _, kwargs = mock_cosmos_container.replace_item.call_args
        assert "etag" in kwargs
        assert kwargs["etag"] == '"etag-1"'

    async def test_counter_etag_conflict_retry(self, mock_cosmos_container):
        mock_cosmos_container.read_item.side_effect = [
            {"id": "orderCounter", "currentValue": 42, "_etag": '"etag-1"'},
            {"id": "orderCounter", "currentValue": 43, "_etag": '"etag-3"'},
        ]
        mock_cosmos_container.replace_item.side_effect = [
            exceptions.CosmosAccessConditionFailedError(
                status_code=412, message="ETag mismatch"
            ),
            {"id": "orderCounter", "currentValue": 44, "_etag": '"etag-4"'},
        ]

        counter = OrderCounter(mock_cosmos_container)
        result = await counter.get_next_id()

        assert result["displayId"] == 44

    async def test_counter_etag_conflict_max_retries(self, mock_cosmos_container):
        mock_cosmos_container.read_item.return_value = {
            "id": "orderCounter",
            "currentValue": 42,
            "_etag": '"etag-1"',
        }
        mock_cosmos_container.replace_item.side_effect = (
            exceptions.CosmosAccessConditionFailedError(
                status_code=412, message="ETag mismatch"
            )
        )

        counter = OrderCounter(mock_cosmos_container, max_retries=0)
        with pytest.raises(CounterConflictError):
            await counter.get_next_id()

    async def test_counter_initial_seed(self, mock_cosmos_container):
        mock_cosmos_container.read_item.side_effect = [
            exceptions.CosmosResourceNotFoundError(
                status_code=404, message="Item not found"
            ),
            {"id": "orderCounter", "currentValue": 0, "_etag": '"etag-new"'},
        ]
        mock_cosmos_container.replace_item.return_value = {
            "id": "orderCounter",
            "currentValue": 1,
            "_etag": '"etag-2"',
        }

        counter = OrderCounter(mock_cosmos_container)
        result = await counter.get_next_id()

        assert result["displayId"] == 1
        assert result["displayOrder"] == "ORD-0001"

    async def test_display_id_formatting(self, mock_cosmos_container):
        mock_cosmos_container.read_item.return_value = {
            "id": "orderCounter", "currentValue": 42, "_etag": '"etag-1"',
        }
        mock_cosmos_container.replace_item.return_value = {
            "id": "orderCounter", "currentValue": 43, "_etag": '"etag-2"',
        }
        counter = OrderCounter(mock_cosmos_container)
        result = await counter.get_next_id()
        assert isinstance(result["displayId"], int)
        assert result["displayId"] == 43
        assert result["displayOrder"] == "ORD-0043"
        assert result["instanceId"].startswith("ORD-0043-")
        assert len(result["instanceId"]) > len("ORD-0043-")

    async def test_display_id_overflow(self, mock_cosmos_container):
        mock_cosmos_container.read_item.return_value = {
            "id": "orderCounter", "currentValue": 999999, "_etag": '"etag-1"',
        }
        mock_cosmos_container.replace_item.return_value = {
            "id": "orderCounter", "currentValue": 1000000, "_etag": '"etag-2"',
        }
        counter = OrderCounter(mock_cosmos_container)
        result = await counter.get_next_id()
        assert result["displayId"] == 1000000
        assert result["displayOrder"] == "ORD-1000000"
        assert result["instanceId"].startswith("ORD-1000000-")

    async def test_counter_concurrent_increments(self, mock_cosmos_container):
        mock_cosmos_container.read_item.side_effect = [
            {"id": "orderCounter", "currentValue": 10, "_etag": '"e1"'},
            {"id": "orderCounter", "currentValue": 10, "_etag": '"e1"'},
            {"id": "orderCounter", "currentValue": 11, "_etag": '"e2"'},
        ]
        mock_cosmos_container.replace_item.side_effect = [
            {"id": "orderCounter", "currentValue": 11, "_etag": '"e2"'},
            exceptions.CosmosAccessConditionFailedError(
                status_code=412, message="ETag mismatch"
            ),
            {"id": "orderCounter", "currentValue": 12, "_etag": '"e3"'},
        ]
        counter = OrderCounter(mock_cosmos_container)
        result_a = await counter.get_next_id()
        result_b = await counter.get_next_id()
        assert result_a["displayId"] == 11
        assert result_b["displayId"] == 12
        assert result_a["displayOrder"] != result_b["displayOrder"]
