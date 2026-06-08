import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.functions import EventGridEvent, HttpRequest

from src.function_app import (
    confirm_handler,
    get_order_status,
    order_validator,
    submit_order,
)


def _raw(fn):
    inner = fn._function._func
    if hasattr(inner, 'client_function'):
        return inner.client_function
    return inner


def _make_request(method: str, body: dict = None, params: dict = None) -> HttpRequest:
    return HttpRequest(
        method=method,
        url="/api/function",
        headers={"Content-Type": "application/json"},
        params=params or {},
        body=json.dumps(body).encode("utf-8") if body else b"",
    )


def _mock_blob_svc():
    svc = AsyncMock()
    svc.get_container_client = MagicMock(return_value=AsyncMock())
    return svc


@pytest.fixture(autouse=True)
def _setup_env():
    with patch.dict(
        "os.environ",
        {
            "COSMOS_DB_ACCOUNT_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
            "COSMOS_DB_DATABASE_NAME": "order-db",
            "AzureWebJobsStorage__blobServiceUri": "https://fakestorage.blob.core.windows.net",
        },
    ), patch(
        "src.function_app.DefaultAzureCredential"
    ) as mock_cred:
        mock_cred.return_value = AsyncMock()
        yield


class TestSubmitOrder:
    async def test_submit_order_valid(self, sample_order, mock_cosmos_container, mock_df_client):
        mock_cosmos_container.read_item.return_value = {
            "id": "orderCounter", "currentValue": 42, "_etag": '"e1"',
        }
        mock_cosmos_container.replace_item.return_value = {
            "id": "orderCounter", "currentValue": 43, "_etag": '"e2"',
        }
        with patch("src.function_app._get_cosmos_container", return_value=mock_cosmos_container), \
             patch("src.function_app._get_blob_service_client", return_value=_mock_blob_svc()):
            req = _make_request("POST", sample_order)
            resp = await _raw(submit_order)(req=req, df_client=mock_df_client)
            assert resp.status_code == 202

    async def test_submit_order_invalid_body(self, mock_cosmos_container, mock_df_client):
        with patch("src.function_app._get_cosmos_container", return_value=mock_cosmos_container), \
             patch("src.function_app._get_blob_service_client", return_value=_mock_blob_svc()):
            req = _make_request("POST", {"invalid": True})
            resp = await _raw(submit_order)(req=req, df_client=mock_df_client)
            assert resp.status_code == 400

    async def test_submit_order_empty_body(self, mock_cosmos_container, mock_df_client):
        with patch("src.function_app._get_cosmos_container", return_value=mock_cosmos_container), \
             patch("src.function_app._get_blob_service_client", return_value=_mock_blob_svc()):
            req = _make_request("POST", None)
            resp = await _raw(submit_order)(req=req, df_client=mock_df_client)
            assert resp.status_code == 400

    async def test_submit_order_counter_error(self, mock_cosmos_container, mock_df_client):
        mock_cosmos_container.read_item.side_effect = Exception("Counter failure")
        with patch("src.function_app._get_cosmos_container", return_value=mock_cosmos_container), \
             patch("src.function_app._get_blob_service_client", return_value=_mock_blob_svc()):
            valid_body = {"customerName": "Test", "customerPhone": "+351911234567", "items": [{"itemId": "1", "name": "Item", "quantity": 1, "unitPrice": 10}], "total": 10, "tax": 2}
            req = _make_request("POST", valid_body)
            resp = await _raw(submit_order)(req=req, df_client=mock_df_client)
            assert resp.status_code == 503

    async def test_submit_order_blob_failure(self, mock_cosmos_container, mock_df_client):
        mock_cosmos_container.read_item.return_value = {
            "id": "orderCounter", "currentValue": 42, "_etag": '"e1"',
        }
        mock_cosmos_container.replace_item.return_value = {
            "id": "orderCounter", "currentValue": 43, "_etag": '"e2"',
        }
        mock_blob = AsyncMock()
        mock_blob.upload_blob.side_effect = Exception("Blob error")
        mock_blob_svc = AsyncMock()
        mock_blob_svc.get_container_client = MagicMock(return_value=mock_blob)
        with patch("src.function_app._get_cosmos_container", return_value=mock_cosmos_container), \
             patch("src.function_app._get_blob_service_client", return_value=mock_blob_svc):
            req = _make_request("POST", {"customerName": "Test", "customerPhone": "+351911234567", "items": [{"itemId": "1", "name": "Item", "quantity": 1, "unitPrice": 10}], "total": 10, "tax": 2})
            resp = await _raw(submit_order)(req=req, df_client=mock_df_client)
            assert resp.status_code == 500


class TestConfirmHandler:
    async def test_confirm_handler_valid(self, mock_df_client):
        mock_df_client.get_status.return_value.status = "Running"
        req = _make_request("POST", {"instance_id": "ORD-0042-abc123"})
        resp = await _raw(confirm_handler)(req=req, df_client=mock_df_client)
        assert resp.status_code == 200

    async def test_confirm_handler_missing_id(self, mock_df_client):
        req = _make_request("POST", {})
        resp = await _raw(confirm_handler)(req=req, df_client=mock_df_client)
        assert resp.status_code == 400

    async def test_confirm_handler_not_found(self, mock_df_client):
        mock_df_client.get_status.return_value.status = None
        req = _make_request("POST", {"instance_id": "unknown"})
        resp = await _raw(confirm_handler)(req=req, df_client=mock_df_client)
        assert resp.status_code == 404

    async def test_confirm_handler_already_completed(self, mock_df_client):
        mock_df_client.get_status.return_value.status = "Completed"
        req = _make_request("POST", {"instance_id": "ORD-0042-abc123"})
        resp = await _raw(confirm_handler)(req=req, df_client=mock_df_client)
        assert resp.status_code == 410


class TestGetOrderStatus:
    async def test_get_order_status_found(self, mock_cosmos_container, valid_order_status):
        mock_cosmos_container.read_item.return_value = valid_order_status
        with patch("src.function_app._get_cosmos_container", return_value=mock_cosmos_container):
            req = HttpRequest("GET", "/api/status", params={"orderId": "ORD-0042-a1b2c3d4"}, body=b"")
            resp = await _raw(get_order_status)(req=req)
            assert resp.status_code == 200

    async def test_get_order_status_not_found(self, mock_cosmos_container):
        mock_cosmos_container.read_item.side_effect = Exception("Not found")
        with patch("src.function_app._get_cosmos_container", return_value=mock_cosmos_container):
            req = HttpRequest("GET", "/api/status", params={"orderId": "unknown"}, body=b"")
            resp = await _raw(get_order_status)(req=req)
            assert resp.status_code == 404

    async def test_get_order_status_missing_param(self, mock_cosmos_container):
        with patch("src.function_app._get_cosmos_container", return_value=mock_cosmos_container):
            req = HttpRequest("GET", "/api/status", params={}, body=b"")
            resp = await _raw(get_order_status)(req=req)
            assert resp.status_code == 400


class TestEventGridTrigger:
    async def test_event_grid_trigger_valid(self, mock_df_client):
        from datetime import datetime, timezone
        event = EventGridEvent(
            id="event-id-001",
            subject="/blobServices/default/containers/orders-inbox/blobs/ORD-0042.json",
            event_type="Microsoft.Storage.BlobCreated",
            data={"url": "https://storage.blob.core.windows.net/orders-inbox/ORD-0042.json"},
            data_version="1.0",
            topic="/subscriptions/test",
            event_time=datetime.now(timezone.utc),
        )
        result = await _raw(order_validator)(event=event, df_client=mock_df_client)
        assert result is not None
