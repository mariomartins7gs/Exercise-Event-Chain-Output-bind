# 08 — Auto-Increment Counter Design

## Problem

Every new order needs a **sequential, human-readable display ID** (e.g., `ORD-0042`) that:
- Never repeats
- Is visible to students immediately after submission
- Propagates through the entire pipeline
- Works in a distributed cloud environment (multiple function instances)

## Why Simple `counter += 1` Fails

In a distributed system, multiple function instances can run concurrently:

```python
# BROKEN — race condition!
def get_next_id():
    current = read_counter()    # Instance A reads: 42
    current = read_counter()    # Instance B reads: 42  ← WRONG!
    write_counter(current + 1)  # Both write: 43        ← DUPLICATE!
```

Both instances read `42`, both write `43` → **duplicate order IDs**.

## Solution: Cosmos DB Optimistic Concurrency (Compare-And-Swap)

### Mechanism

Use Cosmos DB's `_etag` property as an **optimistic lock**:

```
1. Read document → get current value + _etag
2. Increment locally
3. Write with condition: "only succeed if _etag hasn't changed"
4. If condition fails (412 Conflict) → someone else wrote first → retry
```

### Etag CAS Flow

```
Time  Instance A                    Instance B
│     read() -> {v:42, etag:"a"}   read() -> {v:42, etag:"a"}
│     new_v = 43                   new_v = 43
│     replace(etag="a")            replace(etag="a")  
│       ✅ SUCCESS (v:43, etag:b)    ❌ 412 CONFLICT (etag changed!)
│                                 retry: read() -> {v:43, etag:"b"}
│                                       new_v = 44
│                                       replace(etag="b") -> ✅
▼
      Final counter: 44
      Instance A → displayId=43
      Instance B → displayId=44  ← No duplicates!
```

### Implementation

```python
class OrderCounter:
    def __init__(self, container: ContainerProxy, max_retries: int = 3):
        self.container = container
        self.max_retries = max_retries

    async def get_next_id(self) -> dict:
        for attempt in range(self.max_retries + 1):
            try:
                counter = await self.container.read_item(
                    item="orderCounter",
                    partition_key="counter"
                )
                new_value = counter.get("currentValue", 0) + 1

                await self.container.replace_item(
                    item=counter,
                    body={**counter, "currentValue": new_value},
                    etag=counter["_etag"],           # ← THE KEY: pass current etag
                    match_condition=MatchConditions.IfNotModified  # ← fail if changed
                )

                return {
                    "displayId": new_value,
                    "displayOrder": f"ORD-{new_value:04d}",
                    "instanceId": f"ORD-{new_value:04d}-{uuid4().hex[:8]}"
                }

            except exceptions.CosmosResourceNotFoundError:
                # First run — seed with value 0
                await self.container.create_item(
                    body={"id": "orderCounter", "currentValue": 0}
                )
                continue

            except exceptions.CosmosAccessConditionFailedError:
                # _etag mismatch — someone else incremented first
                if attempt == self.max_retries:
                    raise CounterConflictError("Max retries exceeded")
                await asyncio.sleep(0.1 * (2 ** attempt))  # 100ms, 200ms, 400ms
                continue
```

### Key Points for Students

| Concept | Explanation |
|---|---|
| **`_etag`** | Cosmos DB auto-generated version token — changes on every write |
| **`IfNotModified`** | Write condition — server rejects if `_etag` doesn't match |
| **HTTP 412** | Precondition Failed — the etag conflict signal |
| **Exponential backoff** | `100ms, 200ms, 400ms` — avoids thundering herd on retry |
| **Auto-seed** | First call creates `{currentValue: 0}` automatically |
| **`max_retries = 3`** | High enough for occasional conflicts, low enough to fail fast |

### Counter Document in Cosmos DB

```json
{
    "id": "orderCounter",
    "partitionKey": "counter",
    "currentValue": 42,
    "_etag": "\"00001234-0000-0000-0000-000000000000\"",
    "_ts": 1749200000
}
```

### Display ID Formats

| Counter Value | `displayId` | `displayOrder` | `instanceId` |
|---|---|---|---|
| 1 | 1 | `ORD-0001` | `ORD-0001-a1b2c3d4` |
| 42 | 42 | `ORD-0042` | `ORD-0042-e5f6g7h8` |
| 9999 | 9999 | `ORD-9999` | `ORD-9999-i9j0k1l2` |

### Propagation Through Pipeline

Every component receives the `displayOrder`:

| Component | How `displayOrder` is Used |
|---|---|
| `submit_order` | Returned to webapp, written as blob filename |
| Blob name | `ORD-0042.json` |
| Event Grid event | Included in blob metadata |
| Orchestrator | Passed through all activity calls |
| SMS message | `"Order ORD-0042 received. Confirm at: ..."` |
| Cosmos DB document | `{displayOrder: "ORD-0042"}` |
| Table Storage (expired) | `{displayOrder: "ORD-0042"}` |
| Status polling response | Included in every status API response |

### Testing Strategy

| Test | Scenario |
|---|---|
| `test_counter_read_increment` | Normal flow: reads 42 → writes 43 |
| `test_counter_etag_conflict_retry` | First CAS 412 → re-read → second CAS succeeds |
| `test_counter_etag_conflict_max_retries` | All 3 retries fail → `CounterConflictError` |
| `test_counter_initial_seed` | Missing doc → creates 0 → retry → returns 1 |
| `test_counter_concurrent` | Mock race → both instances eventually succeed |

### Why Not Alternatives?

| Alternative | Why Not |
|---|---|
| `counter += 1` in memory | Lost on restart, race condition |
| SQL `IDENTITY` / `AUTO_INCREMENT` | Requires SQL Server — not serverless |
| Durable Entity | More complex, adds DF concept overhead |
| Redis `INCR` | Adds another Azure service (Redis Cache cost) |
| GUID only | Not sequential, students can't track `Order #42` |
| Storage Table optimistic concurrency | Same pattern, but Cosmos DB is already in use |
