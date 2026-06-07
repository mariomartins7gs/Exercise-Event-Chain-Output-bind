import asyncio
from uuid import uuid4

from azure.cosmos import exceptions


class CounterConflictError(Exception):
    pass


class OrderCounter:
    def __init__(self, container, max_retries: int = 3):
        self.container = container
        self.max_retries = max_retries

    async def get_next_id(self) -> dict:
        for attempt in range(self.max_retries + 1):
            try:
                counter = await self.container.read_item(
                    item="orderCounter", partition_key="counter"
                )
                new_value = counter.get("currentValue", 0) + 1
                await self.container.replace_item(
                    item=counter,
                    body={**counter, "currentValue": new_value},
                    etag=counter["_etag"],
                    match_condition="IfNotModified",
                )
                instance_id = f"ORD-{new_value:04d}-{uuid4().hex[:8]}"
                return {
                    "displayId": new_value,
                    "displayOrder": f"ORD-{new_value:04d}",
                    "instanceId": instance_id,
                }
            except exceptions.CosmosResourceNotFoundError:
                await self.container.create_item(
                    body={"id": "orderCounter", "partitionKey": "counter", "currentValue": 0}
                )
                continue
            except exceptions.CosmosAccessConditionFailedError:
                if attempt == self.max_retries:
                    raise CounterConflictError("Max retries exceeded on counter CAS")
                await asyncio.sleep(0.1 * (2 ** attempt))
                continue
