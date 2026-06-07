import json

import pytest
from azure.functions import HttpRequest, HttpResponse

from src.function_app import (
    confirm_handler,
    get_order_status,
    order_validator,
    submit_order,
)


def _make_request(method: str, body: dict = None, params: dict = None) -> HttpRequest:
    return HttpRequest(
        method=method,
        url="/api/function",
        headers={"Content-Type": "application/json"},
        params=params or {},
        body=json.dumps(body).encode("utf-8") if body else b"",
    )


class TestSubmitOrder:
    async def test_submit_order_valid(self, sample_order, mock_cosmos_container, mock_blob_service_client, mock_df_client):
        mock_cosmos_container.read_item.return_value = {
            "id": "orderCounter", "currentValue": 42, "_etag": '"e1"',
        }
        mock_cosmos_container.replace_item.return_value = {
            "id": "orderCounter", "currentValue": 43, "_etag": '"e2"',
        }
        req = _make_request("POST", sample_order)
        resp = await submit_order(req, mock_cosmos_container, mock_blob_service_client, mock_df_client)
        assert resp.status_code == 202

    async def test_submit_order_invalid_body(self, mock_cosmos_container, mock_blob_service_client, mock_df_client):
        req = _make_request("POST", {"invalid": True})
        resp = await submit_order(req, mock_cosmos_container, mock_blob_service_client, mock_df_client)
        assert resp.status_code == 400

    async def test_submit_order_empty_body(self, mock_cosmos_container, mock_blob_service_client, mock_df_client):
        req = _make_request("POST", None)
        resp = await submit_order(req, mock_cosmos_container, mock_blob_service_client, mock_df_client)
        assert resp.status_code == 400

    async def test_submit_order_counter_error(self, mock_cosmos_container, mock_blob_service_client, mock_df_client):
        mock_cosmos_container.read_item.side_effect = Exception("Counter failure")
        valid_body = {"customerName": "Test", "customerPhone": "+351911234567", "items": [{"itemId": "1", "name": "Item", "quantity": 1, "unitPrice": 10}], "total": 10, "tax": 2}
        req = _make_request("POST", valid_body)
        resp = await submit_order(req, mock_cosmos_container, mock_blob_service_client, mock_df_client)
        assert resp.status_code == 503

    async def test_submit_order_blob_failure(self, mock_cosmos_container, mock_blob_service_client, mock_df_client):
        mock_cosmos_container.read_item.return_value = {
            "id": "orderCounter", "currentValue": 42, "_etag": '"e1"',
        }
        mock_cosmos_container.replace_item.return_value = {
            "id": "orderCounter", "currentValue": 43, "_etag": '"e2"',
        }
        mock_blob_service_client.upload_blob.side_effect = Exception("Blob error")
        req = _make_request("POST", {"customerName": "Test", "customerPhone": "+351911234567", "items": [{"itemId": "1", "name": "Item", "quantity": 1, "unitPrice": 10}], "total": 10, "tax": 2})
        resp = await submit_order(req, mock_cosmos_container, mock_blob_service_client, mock_df_client)
        assert resp.status_code == 500


class TestConfirmHandler:
    async def test_confirm_handler_valid(self, mock_df_client):
        mock_df_client.get_status.return_value.status = "Running"
        req = _make_request("POST", {"instance_id": "ORD-0042-abc123"})
        resp = await confirm_handler(req, mock_df_client)
        assert resp.status_code == 200

    async def test_confirm_handler_missing_id(self, mock_df_client):
        req = _make_request("POST", {})
        resp = await confirm_handler(req, mock_df_client)
        assert resp.status_code == 400

    async def test_confirm_handler_not_found(self, mock_df_client):
        mock_df_client.get_status.return_value.status = None
        req = _make_request("POST", {"instance_id": "unknown"})
        resp = await confirm_handler(req, mock_df_client)
        assert resp.status_code == 404

    async def test_confirm_handler_already_completed(self, mock_df_client):
        mock_df_client.get_status.return_value.status = "Completed"
        req = _make_request("POST", {"instance_id": "ORD-0042-abc123"})
        resp = await confirm_handler(req, mock_df_client)
        assert resp.status_code == 410


class TestGetOrderStatus:
    async def test_get_order_status_found(self, mock_cosmos_container, valid_order_status):
        mock_cosmos_container.read_item.return_value = valid_order_status
        req = HttpRequest("GET", "/api/status", params={"orderId": "ORD-0042-a1b2c3d4"}, body=b"")
        resp = await get_order_status(req, mock_cosmos_container)
        assert resp.status_code == 200

    async def test_get_order_status_not_found(self, mock_cosmos_container):
        mock_cosmos_container.read_item.side_effect = Exception("Not found")
        req = HttpRequest("GET", "/api/status", params={"orderId": "unknown"}, body=b"")
        resp = await get_order_status(req, mock_cosmos_container)
        assert resp.status_code == 404

    async def test_get_order_status_missing_param(self, mock_cosmos_container):
        req = HttpRequest("GET", "/api/status", params={}, body=b"")
        resp = await get_order_status(req, mock_cosmos_container)
        assert resp.status_code == 400


class TestEventGridTrigger:
    async def test_event_grid_trigger_valid(self, valid_event_grid_event, mock_df_client):
        result = await order_validator(valid_event_grid_event, mock_df_client)
        assert result is not None
