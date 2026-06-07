# 03 — Implementation Sequence

## Dependency Order (TDD: test → code → pass)

```
Phase 0: Project Setup
├── requirements.txt
├── pytest.ini
├── conftest.py
└── test/fixtures/*.json

Phase 1: Data Layer (no external deps)
├── src/models.py          →  test/test_models.py

Phase 2: Core Business Logic
├── src/counter.py         →  test/test_counter.py
├── src/activities.py      →  test/test_activities.py

Phase 3: Orchestration
├── src/orchestrator.py    →  test/test_orchestrator.py

Phase 4: Triggers & Entry Point
├── src/function_app.py    →  test/test_function_app.py

Phase 5: Webapp Frontend
├── webapp/index.html
├── webapp/style.css
└── webapp/app.js

Phase 6: Infrastructure & CI/CD
├── infra/main.bicep
├── .github/workflows/deploy.yml
├── host.json
└── local.settings.json

Phase 7: Documentation
├── README.md
└── docs/.md
```

---

## Phase 0 — Project Setup

### `requirements.txt`

```
azure-functions
azure-functions-durable
pydantic>=2.0
azure-cosmos>=4.3.0
azure-communication-sms>=1.0.0
azure-storage-blob>=12.15.0
azure-storage-table>=12.4.0
azure-identity>=1.12.0

# Dev (not deployed)
pytest>=7.0
pytest-asyncio>=0.21
pytest-cov>=4.0
pytest-mock>=3.10
httpx>=0.24
```

### `pytest.ini`

```ini
[pytest]
testpaths = test
python_files = test_*.py
python_functions = test_*
asyncio_mode = auto
markers =
    unit: Unit tests (fast, no infrastructure)
    integration: Integration tests (Azurite/Cosmos emulator)
    e2e: End-to-end pipeline tests
    slow: Tests that take >5s
```

### `conftest.py`

Shared fixtures: `sample_order`, `mock_cosmos_container`, `mock_acs_client`, `mock_df_context`, `mock_df_client`, `valid_event_grid_event`, `load_json`.

### Fixture JSON files

- `sample_order.json` — valid order payload
- `valid_counter_doc.json` — counter doc with `_etag`
- `invalid_order_no_items.json` — validation error case
- `expired_order_entry.json` — Table Storage entity shape

---

## Phase 1 — Data Layer

### `src/models.py`

**Dependencies**: `pydantic`, `typing`, `datetime`, `enum`

**Classes**:

```python
class OrderItem(BaseModel):
    itemId: str
    name: str = Field(..., min_length=1, max_length=200)
    quantity: int = Field(..., ge=1, le=999)
    unitPrice: float = Field(..., ge=0)

class OrderPayload(BaseModel):
    customerName: str = Field(..., min_length=1, max_length=100)
    customerPhone: str = Field(..., pattern=r"^\+?[1-9]\d{6,14}$")
    items: list[OrderItem] = Field(..., min_length=1)
    total: float = Field(..., ge=0)
    tax: float = Field(..., ge=0)
    notes: Optional[str] = Field(None, max_length=500)

class CounterDocument(BaseModel):
    id: str = "orderCounter"
    currentValue: int = Field(default=0, ge=0)

class SmsRequest(BaseModel):
    phoneNumber: str
    message: str = Field(..., min_length=1, max_length=160)
    orderId: str

class SmsResult(BaseModel):
    messageId: str
    status: Literal["sent", "failed"]
    errorMessage: Optional[str] = None

class OrderStatus(str, Enum):
    SUBMITTED = "submitted"
    VALIDATING = "validating"
    SMS_SENT = "sms_sent"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    EXPIRED = "expired"

class StatusUpdate(BaseModel):
    orderId: str
    status: OrderStatus
    timestamp: datetime
    details: Optional[str] = None

class FinalOrder(BaseModel):
    id: str
    instanceId: str
    displayId: int
    displayOrder: str
    customerName: str
    customerPhone: str
    items: list[OrderItem]
    total: float
    tax: float
    notes: Optional[str] = None
    status: OrderStatus
    timeline: list[StatusUpdate] = []
    createdAt: datetime
    expiresAt: Optional[datetime] = None
    confirmedAt: Optional[datetime] = None
    confirmationData: Optional[dict] = None

class OrderStatusResponse(BaseModel):
    orderId: str
    displayId: int
    displayOrder: str
    status: OrderStatus
    timeline: list[StatusUpdate]
    expiresAt: Optional[datetime] = None
    secondsRemaining: Optional[int] = None

class ExpiredOrder(BaseModel):
    PartitionKey: str
    RowKey: str
    orderId: str
    displayOrder: str
    customerName: str
    customerPhone: str
    total: float
    expiresAt: str
    reason: str = "Customer did not confirm within 3 minutes"
```

---

## Phase 2a — Counter Logic

### `src/counter.py`

```python
class CounterConflictError(Exception): pass

class OrderCounter:
    """Cosmos DB optimistic concurrency (ETag CAS) counter."""
    
    def __init__(self, container: ContainerProxy, max_retries: int = 3): ...
    
    async def get_next_id(self) -> dict:
        """
        Atomic CAS increment.
        Retries on CosmosAccessConditionFailedError with exponential backoff.
        Auto-seeds counter doc on CosmosResourceNotFoundError.
        
        Returns: { displayId, displayOrder, instanceId }
        """
        for attempt in range(self.max_retries + 1):
            try:
                counter = await self.container.read_item(...)
                new_value = counter["currentValue"] + 1
                await self.container.replace_item(
                    item=counter, body={...},
                    etag=counter["_etag"],
                    match_condition=MatchConditions.IfNotModified
                )
                return {
                    "displayId": new_value,
                    "displayOrder": f"ORD-{new_value:04d}",
                    "instanceId": f"ORD-{new_value:04d}-{uuid4().hex[:8]}"
                }
            except CosmosResourceNotFoundError:
                await self.container.create_item({"id": "orderCounter", "currentValue": 0})
                continue
            except CosmosAccessConditionFailedError:
                if attempt == self.max_retries: raise CounterConflictError(...)
                await asyncio.sleep(0.1 * (2 ** attempt))
                continue
```

---

## Phase 2b — Activity Functions

### `src/activities.py`

**Functions** (7 activities):

| Function | Decorator | Input | Output | Side Effect |
|---|---|---|---|---|
| `validate_order` | `@activity_trigger` | payload dict | validated dict | — (pure) |
| `get_next_counter` | `@activity_trigger` | _ | `{displayId, displayOrder, instanceId}` | Cosmos DB CAS |
| `send_sms` | `@activity_trigger` | `{phone, message, orderId}` | `SmsResult` dict | ACS API call |
| `write_status_update` | `@activity_trigger` | `{orderId, status, ts, ...}` | updated doc dict | Cosmos DB upsert |
| `process_order` | `@activity_trigger` | order_data dict | enriched dict | — (pure) |
| `write_to_cosmos` | `@activity_trigger` | order_document dict | written dict | Cosmos DB upsert |
| `log_expired_order` | `@activity_trigger` | expired_order dict | None | Table Storage insert |

All activities use `DefaultAzureCredential()` for auth, read endpoints from `os.environ`, and log entry/exit.

---

## Phase 3 — Orchestrator

### `src/orchestrator.py`

**Key rules for DF determinism**:
- ✅ Use `context.current_utc_datetime` (NOT `datetime.now()`)
- ✅ Use `context.call_activity()` for all side effects
- ✅ All inputs/outputs = JSON-serializable dicts
- ❌ NO `random`, `uuid`, `datetime.now`, direct I/O

```python
@bp.orchestration_trigger(context_name="context")
def order_workflow(context: DurableOrchestrationContext) -> dict:
    order = context.get_input()
    
    # 1. Validate
    validated = yield context.call_activity("validate_order", order)
    
    # 2. Counter
    counter = yield context.call_activity("get_next_counter", {})
    validated.update(counter)
    
    # 3-6. Status updates + SMS
    yield context.call_activity("write_status_update", {...})  # validating
    yield context.call_activity("send_sms", {...})              # SMS
    yield context.call_activity("write_status_update", {...})  # sms_sent
    yield context.call_activity("write_status_update", {...})  # pending_confirmation
    
    # 7. RACE: Timer vs External Event
    expiry = context.current_utc_datetime + timedelta(seconds=180)
    timer_task = context.create_timer(expiry)
    event_task = context.wait_for_external_event("Confirmed")
    winner = yield context.task_any([timer_task, event_task])
    
    if winner == timer_task:
        # EXPIRED PATH
        yield context.call_activity("write_status_update", {...status="expired"...})
        yield context.call_activity("log_expired_order", validated)
        return {**counter, "status": "expired"}
    else:
        # CONFIRMED PATH
        confirmed = yield context.call_activity("process_order", validated)
        yield context.call_activity("write_status_update", {...status="confirmed"...})
        yield context.call_activity("write_to_cosmos", confirmed)
        return {**counter, "status": "completed"}
```

---

## Phase 4 — Triggers & Entry Point

### `src/function_app.py`

**4 trigger functions**:

| Function | Decorator | Route/Trigger | Key Logic |
|---|---|---|---|
| `submit_order` | `@app.route` | `POST /api/submit_order` | Parse → validate → counter → write blob → return 202 |
| `confirm_handler` | `@app.route` | `POST /api/confirm_handler` | Get instance_id → check status → raise_event → return |
| `get_order_status` | `@app.route` | `GET /api/status` | Read Cosmos DB → calculate countdown → return JSON |
| `order_validator` | `@app.event_grid_trigger` | `BlobCreated` | Read blob → start DF orchestration |

---

## Phase 5 — Webapp

### `webapp/index.html`

- **Left panel**: Order form (customer name, phone, items dynamic list, notes)
- **Right panel**: Live status dashboard (hidden until submission)
- **Dashboard**: displayOrder, status badge, progress bar, countdown timer, timeline stepper, confirm button

### `webapp/style.css`

- Clean, modern classroom design
- Status badges: green (completed), red (expired), orange (pending), blue (processing)
- Vertical timeline with colored dots
- Animated progress bar
- Responsive (mobile via flexbox/grid)

### `webapp/app.js`

| Function | Purpose |
|---|---|
| `validateForm()` | Client-side validation matching Pydantic rules |
| `submitOrder(data)` | `POST /api/submit_order` |
| `startPolling(orderId)` | `setInterval` every 5s |
| `fetchStatus(orderId)` | `GET /api/status?orderId=X` |
| `renderStatus(data)` | Update all dashboard sections |
| `renderTimeline(timeline)` | Render vertical stepper |
| `renderCountdown(seconds)` | MM:SS countdown display |
| `renderProgressBar(status, remaining)` | Animated bar |
| `confirmOrder()` | `POST /api/confirm_handler` |
| `stopPolling()` | `clearInterval` |

---

## Phase 6 — Infrastructure + CI/CD

### `infra/main.bicep`

**Resources**: Storage Account, Event Grid System Topic, Function App, App Insights, Cosmos DB, ACS, RBAC assignments.

### `.github/workflows/deploy.yml`

**6 jobs**: Lint → Test → Build → Deploy Infra → Deploy Functions → Deploy Webapp

### `host.json`, `local.settings.json`

Configuration for both local dev (Azurite + emulator) and Azure (Managed Identity).

---

## Phase 7 — Documentation

9 docs in `docs/`:
1. Architecture overview (this)
2. TDD test plan
3. Implementation sequence (this)
4. Infrastructure Bicep
5. CI/CD pipeline
6. Cost analysis
7. Student exercise guide
8. Auto-increment counter design
9. Live status tracking design
