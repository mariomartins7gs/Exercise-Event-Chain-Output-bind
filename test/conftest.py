import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_json(filename: str) -> dict:
    with open(FIXTURES_DIR / filename) as f:
        return json.load(f)


@pytest.fixture
def sample_order():
    return load_json("sample_order.json")


@pytest.fixture
def invalid_order_no_items():
    return load_json("invalid_order_no_items.json")


@pytest.fixture
def valid_counter_doc():
    return load_json("valid_counter_doc.json")


@pytest.fixture
def expired_order_entry():
    return load_json("expired_order_entry.json")


@pytest.fixture
def valid_order_status():
    return load_json("valid_order_status.json")


@pytest.fixture
def mock_cosmos_container(mocker):
    container = AsyncMock()
    container.read_item = AsyncMock()
    container.replace_item = AsyncMock()
    container.create_item = AsyncMock()
    container.upsert_item = AsyncMock()
    return container


@pytest.fixture
def mock_acs_client(mocker):
    client = AsyncMock()
    client.send = AsyncMock(return_value=[MagicMock(message_id="mock-msg-id")])
    return client


@pytest.fixture
def mock_blob_service_client(mocker):
    client = AsyncMock()
    client.upload_blob = AsyncMock()
    client.download_blob = AsyncMock()
    return client


@pytest.fixture
def mock_table_service_client(mocker):
    client = AsyncMock()
    client.create_entity = AsyncMock()
    return client


@pytest.fixture
def mock_df_client(mocker):
    client = AsyncMock()
    client.start_new_orchestration = AsyncMock(
        return_value=MagicMock(instance_id="ORD-0042-a1b2c3d4")
    )
    client.raise_event = AsyncMock()
    client.get_status = AsyncMock()
    return client


@pytest.fixture
def valid_event_grid_event():
    return {
        "id": "event-id-001",
        "subject": "/blobServices/default/containers/orders-inbox/blobs/ORD-0042.json",
        "event_type": "Microsoft.Storage.BlobCreated",
        "data": {
            "url": "https://storage.blob.core.windows.net/orders-inbox/ORD-0042.json",
            "eTag": "0x8D8",
            "contentLength": 256,
        },
    }
