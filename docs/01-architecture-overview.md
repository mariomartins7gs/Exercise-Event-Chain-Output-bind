# 01 — Architecture Overview

## Complete Pipeline Fluxogram

```mermaid
flowchart TB
    subgraph INPUT["📥 INPUT LAYER — Student via Webapp"]
        A1["Student opens webapp\n(order-form.html)"] --> A2["Fills form: customer,\nitems, address, phone"]
        A2 --> A3["POST /api/submit_order\n(HTTP Function)"]
        A3 --> A4["Counter: get_next_id\n(Cosmos DB optimistic concurrency)"]
        A4 --> A5["Function writes order.json\nto Blob container 'orders-inbox'"]
    end

    subgraph TRIGGER["⚡ EVENT GRID LAYER"]
        B1["BlobCreated event fires\nautomatically"] --> B2["Event Grid System Topic\n(routing to Function App)"]
    end

    subgraph PROCESS["⚙️ PROCESSING LAYER — Function App"]
        direction TB
        
        C1["order_validator\n(EventGridTrigger)"] --> C2["Reads blob content\nExtracts order payload"]
        C2 --> C3["Starts DF Orchestration\nclient.start_new()"]

        subgraph DURABLE["⏳ Durable Orchestration (3-min window)"]
            D1["Activity: validate_order\n(Pydantic schema validation)"] --> D2["Activity: get_next_counter\n(Cosmos DB CAS)"]
            D2 --> D3["Activity: write_status_update\n(status='validating')"]
            D3 --> D4["Activity: send_sms\nvia Azure Communication Services"]
            D4 --> D5["Activity: write_status_update\n(status='sms_sent')"]
            D5 --> D6["Activity: write_status_update\n(status='pending_confirmation')"]
            D6 --> D7{"⏰ RACE: Timer(180s)\nvs\nWaitForExternalEvent?"}
            D7 -->|"📱 Confirmed within 3min"| D8["Activity: process_order\n(enrich: totals, tax, status)"]
            D8 --> D9["Activity: write_status_update\n(status='confirmed')"]
            D9 --> D10["Activity: write_to_cosmos\n(status: 'Confirmed')"]
            D7 -->|"⏳ Timer expires (3min)"| D11["Activity: write_status_update\n(status='expired')"]
            D11 --> D12["Activity: log_expired_order\n(Table Storage)"]
        end

        C3 --> D1

        subgraph CALLBACK["📞 SMS Callback"]
            E1["Student receives SMS:\n'Confirm Order ORD-0042\nat /api/confirm_handler'"] --> E2["Student clicks link\nor POST via webapp"]
            E2 --> E3["confirm_handler\n(HTTP Trigger)"]
            E3 --> E4["Validates instance_id\nChecks orchestration status"]
            E4 --> E5["RaisesEvent('Confirmed')\nto orchestrator instance"]
            E5 --> D7
        end

        subgraph STATUS["📊 Live Status (Webapp Polling)"]
            F1["Webapp polls every 5s\nGET /api/status?orderId=X"] --> F2["HTTP Trigger reads\nCosmos DB status container"]
            F2 --> F3["Returns timeline,\ncurrent status, countdown"]
            F3 --> F4["Renders dashboard\n(stepper, timer, progress)"]
        end
    end

    subgraph OUTPUT["📤 OUTPUT LAYER"]
        O1["Cosmos DB\ncontainer: Orders\ndocuments with status:'Completed'"]
        O2["Cosmos DB\ncontainer: OrderStatus\ntimeline documents"]
        O3["Storage Table\nOrdersHistory\ndocuments with status:\n'NotConfirmed'"]
        O4["Blob Storage\n$web container\nstatic website hosting"]
        O5["Application Insights\nFull trace of:\n- Orchestration steps\n- Duration per activity\n- SMS delivery status\n- Final disposition"]
    end

    D10 --> O1
    D12 --> O3
    A3 -.-> O4
    D1 -.->|"telemetry"| O5
    D4 -.-> O5
    D7 -.-> O5
    D8 -.-> O5
    F2 -.-> O2

    style A1 fill:#e1f5fe,stroke:#0288d1
    style A3 fill:#e1f5fe,stroke:#0288d1
    style B1 fill:#fff3e0,stroke:#f57c00
    style C1 fill:#e8f5e9,stroke:#388e3c
    style D7 fill:#fce4ec,stroke:#d32f2f
    style O1 fill:#f3e5f5,stroke:#7b1fa2
    style O2 fill:#f3e5f5,stroke:#7b1fa2
    style O3 fill:#f3e5f5,stroke:#7b1fa2
    style O5 fill:#f3e5f5,stroke:#7b1fa2
```

## Component Responsibilities

| Component | Type | Trigger | Responsibility |
|---|---|---|---|
| `submit_order` | HTTP Trigger | `POST /api/submit_order` | Validate payload, get counter ID, write blob, return tracking info |
| `order_validator` | EventGrid Trigger | `BlobCreated` on `orders-inbox` | Read blob, start DF orchestration |
| `order_workflow` | DF Orchestrator | `start_new_orchestration` | Orchestrate the 8-step pipeline with timer/event race |
| `confirm_handler` | HTTP Trigger | `POST /api/confirm_handler` | Raise "Confirmed" event to orchestrator |
| `get_order_status` | HTTP Trigger | `GET /api/status` | Read status from Cosmos DB, return timeline + countdown |
| `validate_order` | Activity | Called by orchestrator | Pydantic schema validation |
| `get_next_counter` | Activity | Called by orchestrator | Atomic counter increment (CAS) |
| `send_sms` | Activity | Called by orchestrator | Send SMS via ACS (or simulated) |
| `write_status_update` | Activity | Called by orchestrator | Persist timeline entry to Cosmos DB |
| `process_order` | Activity | Called by orchestrator | Enrich with status, timestamps, totals |
| `write_to_cosmos` | Activity | Called by orchestrator | Write final order document |
| `log_expired_order` | Activity | Called by orchestrator | Write to Table Storage with `NotConfirmed` |

## Data Flow — Confirmed Path

```
1. Webapp POST → submit_order
2.   → Cosmos DB: counter.get_next_id() → displayId=42
3.   → Blob: orders-inbox/ORD-0042.json
4.   → Event Grid: BlobCreated
5.   → order_validator reads blob
6.   → DF orchestration starts (instance_id = ORD-0042-abc123)
7.   → validate_order (Pydantic)
8.   → get_next_counter (CAS retry)
9.   → write_status_update (validating)
10.  → send_sms (ACS)
11.  → write_status_update (sms_sent)
12.  → write_status_update (pending_confirmation, expiresAt)
13.  → RACE: Timer(180s) vs WaitForExternalEvent
14.  → Student clicks SMS link → POST /api/confirm_handler
15.  → RaiseEvent("Confirmed") → timer task wins
16.  → process_order (enrich)
17.  → write_status_update (confirmed)
18.  → write_to_cosmos (Orders container)
19.  → Webapp polls GET /api/status → sees "completed"
```

## Data Flow — Expired Path (Steps 1-13 same)

```
14.  → Timer expires (3 min)
15.  → write_status_update (expired)
16.  → log_expired_order (Table Storage: ExpiredOrders)
17.  → Webapp polls GET /api/status → sees "expired"
```

## Azure Resources (One Resource Group)

| Resource | SKU | Purpose |
|---|---|---|
| Storage Account | Standard_LRS | Blob containers, Tables, Static website |
| Event Grid System Topic | Standard | Route BlobCreated events to Function |
| Function App | Consumption (Y1) | All triggers + DF orchestration |
| Cosmos DB | Free Tier (Serverless) | Orders, Counter, Status containers |
| App Insights | Basic | Telemetry + distributed tracing |
| ACS | Free Tier | SMS delivery |

## RBAC Roles (System-assigned Managed Identity)

| Identity | Scope | Role |
|---|---|---|
| Function App MI | Storage Account | Storage Blob Data Contributor |
| Function App MI | Storage Account | Storage Table Data Contributor |
| Function App MI | Cosmos DB | Cosmos DB Built-in Data Contributor |
| Function App MI | ACS | ACS SMS Sender |
| Function App MI | App Insights | Monitoring Metrics Publisher |
