import json
import os
from functools import lru_cache

import azure.durable_functions as df
import azure.functions as func

app = func.FunctionApp()

COSMOS_ACCOUNT = os.environ.get("COSMOS_DB_ACCOUNT_ENDPOINT", "")
COSMOS_DATABASE = os.environ.get("COSMOS_DB_DATABASE_NAME", "order-db")
COSMOS_ORDERS = os.environ.get("COSMOS_DB_CONTAINER_ORDERS", "Orders")
STORAGE_ACCOUNT = os.environ.get("AzureWebJobsStorage__accountName", "")
STORAGE_INBOX = "orders-inbox"


async def _get_cosmos():
    from azure.cosmos.aio import CosmosClient
    from azure.identity.aio import DefaultAzureCredential
    cred = DefaultAzureCredential()
    client = CosmosClient(COSMOS_ACCOUNT, credential=cred)
    db = client.get_database_client(COSMOS_DATABASE)
    return db.get_container_client(COSMOS_ORDERS)


async def _get_blob():
    from azure.storage.blob.aio import BlobServiceClient
    from azure.identity.aio import DefaultAzureCredential
    cred = DefaultAzureCredential()
    client = BlobServiceClient(
        f"https://{STORAGE_ACCOUNT}.blob.core.windows.net", credential=cred,
    )
    return client.get_container_client(STORAGE_INBOX)


@app.route(route="ping", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def ping(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("pong", status_code=200)


@app.route(route="submit_order", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
@app.durable_client_input(client_name="client")
async def submit_order_trigger(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    from src.function_app import submit_order
    cosmos = await _get_cosmos()
    blob = await _get_blob()
    return await submit_order(req, cosmos, blob, client)


@app.route(route="confirm_handler", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
@app.durable_client_input(client_name="client")
async def confirm_handler_trigger(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    from src.function_app import confirm_handler
    return await confirm_handler(req, client)


@app.route(route="get_order_status", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
async def get_order_status_trigger(req: func.HttpRequest) -> func.HttpResponse:
    from src.function_app import get_order_status
    cosmos = await _get_cosmos()
    return await get_order_status(req, cosmos)


@app.event_grid_trigger(arg_name="event")
async def event_grid_trigger(event: func.EventGridEvent):
    return json.dumps({"status": "received"})


@app.orchestration_trigger(context_name="context")
@app.function_name("order_workflow")
def order_workflow_orchestrator(context: df.DurableOrchestrationContext):
    from src.orchestrator import order_workflow
    return order_workflow(context)


@app.activity_trigger(input_name="input")
@app.function_name("validate_order")
def validate_order_activity(input: dict) -> dict:
    from src.activities import validate_order
    return validate_order(input)


@app.activity_trigger(input_name="input")
@app.function_name("get_next_counter")
async def get_next_counter_activity(input: dict) -> dict:
    from src.activities import get_next_counter
    cosmos = await _get_cosmos()
    return await get_next_counter(cosmos)


@app.activity_trigger(input_name="input")
@app.function_name("send_sms")
def send_sms_activity(input: dict) -> dict:
    from src.activities import send_sms
    from azure.communication.sms.aio import SmsClient
    from azure.identity.aio import DefaultAzureCredential
    import asyncio

    async def _send():
        acs_endpoint = os.environ.get("ACS_ENDPOINT", "")
        cred = DefaultAzureCredential()
        async with SmsClient(endpoint=acs_endpoint, credential=cred) as acs_client:
            return await send_sms(input, acs_client)

    return asyncio.get_event_loop().run_until_complete(_send())


@app.activity_trigger(input_name="input")
@app.function_name("write_status_update")
async def write_status_update_activity(input: dict) -> dict:
    from src.activities import write_status_update
    cosmos = await _get_cosmos()
    return await write_status_update(input, cosmos)


@app.activity_trigger(input_name="input")
@app.function_name("process_order")
def process_order_activity(input: dict) -> dict:
    from src.activities import process_order
    return process_order(input)


@app.activity_trigger(input_name="input")
@app.function_name("write_to_cosmos")
async def write_to_cosmos_activity(input: dict) -> dict:
    from src.activities import write_to_cosmos
    cosmos = await _get_cosmos()
    return await write_to_cosmos(input, cosmos)


@app.activity_trigger(input_name="input")
@app.function_name("log_expired_order")
def log_expired_order_activity(input: dict) -> dict:
    from src.activities import log_expired_order
    from azure.data.tables.aio import TableServiceClient
    from azure.identity.aio import DefaultAzureCredential
    import asyncio

    async def _log():
        cred = DefaultAzureCredential()
        async with TableServiceClient(
            f"https://{STORAGE_ACCOUNT}.table.core.windows.net", credential=cred,
        ) as tsc:
            return await log_expired_order(input, tsc)

    return asyncio.get_event_loop().run_until_complete(_log())
