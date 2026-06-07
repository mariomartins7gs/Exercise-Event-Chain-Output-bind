# Exercise-Event-Chain-Output-bind — Master Plan

## Project Overview

An **Azure Functions Python v2** event-driven order processing pipeline with SMS confirmation, designed as a classroom exercise for **Azure for Students** subscriptions.

### Core Architecture

```
[HTML Webapp] → POST /api/submit_order → [submit_order HTTP]
    → Writes order.json to Blob container "orders-inbox"
        → Event Grid System Topic (BlobCreated)
            → order_validator (EventGridTrigger)
                → Starts Durable Functions orchestration
                    → validate_order (activity)
                    → get_next_counter (activity — Cosmos DB optimistic concurrency)
                    → send_sms via ACS (activity)
                    → RACE: Timer(180s) vs WaitForExternalEvent("Confirmed")
                        ├─ Confirmed → process_order → write_to_cosmos (status="Confirmed")
                        └─ Timeout   → log_expired → Table Storage (status="NotConfirmed")
                    ← confirm_handler (HTTP Trigger) raises event to orchestrator
                ← get_order_status (HTTP Trigger) — live polling
```

### Tech Stack

| Component | Technology |
|---|---|
| Runtime | Azure Functions Python v2 (`func.FunctionApp()`) |
| Workflow | Durable Functions (orchestrator + activities) |
| Event Source | Event Grid System Topic (Blob Storage) |
| Database | Cosmos DB (free tier) — order state + counter |
| Messaging | Azure Communication Services (SMS, free tier) |
| Auth | Managed Identity + RBAC (zero connection strings) |
| Frontend | Blob Storage static website (HTML/CSS/JS) |
| IaC | Bicep |
| CI/CD | GitHub Actions |
| Observability | Application Insights |

### Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Orchestration | Durable Functions | Canonical pattern for `WaitForExternalEvent` + `CreateTimer` race |
| Counter | Cosmos DB optimistic concurrency (ETag CAS) | Teaches distributed systems pattern, no new services |
| SMS | Azure Communication Services (switchable to simulated) | Real SMS with free tier, teaches another Azure service |
| Auth | Managed Identity | Best practice, teaches Entra ID + RBAC |
| Event Source | System Topic (Blob Storage) | Student uploads trigger the pipeline |
| IaC | Bicep | Azure-native, simpler for classroom |
| File structure | 4 files (`function_app.py`, `orchestrator.py`, `activities.py`, `models.py` + `counter.py`) | DF determinism requires separation |

## Project Structure

```
Exercise-Event-Chain-Output-bind/
│
├── PLAN.md                              ← This file — master plan
├── .github/workflows/deploy.yml         ← CI/CD pipeline (planned)
│
├── src/
│   ├── function_app.py                  ← Entry: HTTP + Event Grid triggers
│   ├── orchestrator.py                  ← DF workflow (deterministic)
│   ├── activities.py                    ← Activity functions
│   ├── counter.py                       ← Cosmos DB optimistic concurrency counter
│   └── models.py                        ← Pydantic schemas
│
├── webapp/
│   ├── index.html                       ← Order form + live dashboard
│   ├── style.css                        ← Styling
│   └── app.js                           ← Client-side logic + polling
│
├── infra/
│   └── main.bicep                       ← All Azure resources + RBAC
│
├── test/
│   ├── conftest.py                      ← Shared fixtures + mocks
│   ├── fixtures/                        ← JSON test data
│   │   ├── sample_order.json
│   │   ├── valid_counter_doc.json
│   │   ├── invalid_order_no_items.json
│   │   └── expired_order_entry.json
│   ├── test_models.py                   ← Pydantic validation tests (~10)
│   ├── test_counter.py                  ← CAS concurrency tests (~8)
│   ├── test_activities.py               ← Activity isolation tests (~12)
│   ├── test_orchestrator.py             ← DF determinism tests (~6)
│   └── test_function_app.py             ← Trigger integration tests (~13)
│
├── docs/
│   ├── 01-architecture-overview.md      ← Pipeline detail + fluxogram
│   ├── 02-tdd-test-plan.md              ← ~60 tests organized by component
│   ├── 03-implementation-sequence.md    ← 8 phases, file-by-file, dep order
│   ├── 04-infrastructure-bicep.md       ← Azure resources + RBAC + deployment
│   ├── 05-cicd-pipeline.md              ← GitHub Actions workflow
│   ├── 06-cost-analysis.md              ← $0.65/month breakdown
│   ├── 07-student-exercise-guide.md     ← 6-part classroom lab (3-4h)
│   ├── 08-auto-increment-counter.md     ← Optimistic concurrency design
│   ├── 09-live-status-tracking.md       ← Polling architecture
│   └── adr/                             ← Architecture Decision Records
│       ├── adr-001-durable-functions.md
│       ├── adr-002-optimistic-concurrency.md
│       ├── adr-003-managed-identity.md
│       ├── adr-004-cosmos-for-state.md
│       └── adr-005-acs-sms.md
│
├── requirements.txt                     ← Python dependencies
├── host.json                            ← Functions host config
├── local.settings.json                  ← Local dev settings
├── .funcignore                          ← Deployment exclusions
└── pytest.ini                           ← Test configuration
```

## Methodology

This project follows **SDD → TDD → Code** discipline:

```
Spec-Driven Development (SDD) — docs/10-sdd-workflow.md
  ↓
Test-Driven Development (TDD) — write tests first (Red → Green → Refactor)
  ↓
MVP/KPI gates — docs/11-mvp-kpi-definition.md (minimum integrity thresholds)
```

All phases produce specs and tests **before** implementation code. KPIs are evaluated at every phase.

## Implementation Phases

| Phase | What | Files | Tests | Time |
|---|---|---|---|---|
| 0 | SDD + KPI framework | `docs/10-sdd-workflow.md`, `docs/11-mvp-kpi-definition.md` | — | 30m |
| 1 | Data models (spec + tests) | `src/models.py` | `test_models.py` (10) | 45m |
| 2a | Counter logic (spec + tests) | `src/counter.py` | `test_counter.py` (8) | 45m |
| 2b | Activity functions (spec + tests) | `src/activities.py` | `test_activities.py` (12) | 90m |
| 3 | Orchestrator (spec + tests) | `src/orchestrator.py` | `test_orchestrator.py` (6) | 60m |
| 4 | Triggers (spec + tests) | `src/function_app.py` | `test_function_app.py` (13) | 90m |
| 5 | Webapp frontend | `webapp/index.html`, `style.css`, `app.js` | — | 60m |
| 6 | Infrastructure (Bicep) | `infra/main.bicep` | `az deployment validate` | 60m |
| 7 | CI/CD | `.github/workflows/deploy.yml` | — | 30m |
| 8 | Documentation | All `/docs/*.md` | — | 60m |
| **Total** | | | **~59 tests** | **~9h** |

## KPI Gates (per phase)

| KPI | Target | Check |
|-----|--------|-------|
| Test pass rate | 100% critical path | `pytest --tb=short` |
| Line coverage | ≥80% overall | `pytest --cov=src` |
| Module coverage | models:100%, counter:95%, activities:90%, orchestrator:95%, function_app:85% | `pytest --cov --cov-report=term-missing` |
| Type safety | Zero mypy errors | `mypy src/` |
| Auth surface | Zero connection strings | `grep -r "AccountKey\|connectionString" src/` |
| Determinism | No `datetime.now()`/`random`/`uuid` in orchestrator | Code review |

## Cost (Azure for Students)

| Resource | Monthly Cost |
|---|---|
| Function App (Consumption) | $0.00 (1M free exec) |
| Cosmos DB (Free Tier) | $0.00 (1000 RU/s + 25 GB) |
| Storage Account | ~$0.05 |
| App Insights | $0.00 (5 GB free) |
| Event Grid | ~$0.60 |
| ACS SMS (Free Tier) | $0.00 (200 SMS/mo) |
| **Total** | **~$0.65/mo** |

## Pipeline Detail

### Status State Machine

```
submitted ──▶ validating ──▶ sms_sent ──▶ pending_confirmation
                                               │           │
                                          [confirm]    [timeout]
                                               │           │
                                           confirmed    expired
                                               │
                                           processing
                                               │
                                           completed
```

### Auto-Increment Display ID

- **Type**: Cosmos DB document with `_etag`-based Compare-And-Swap (CAS)
- **Format**: `ORD-{value:04d}` (e.g., `ORD-0042`)
- **Retry**: Exponential backoff (100ms, 200ms, 400ms), max 3 retries
- **Seed**: Auto-created on first use (`currentValue: 0`)

### Live Status Tracking

- **Polling**: Webapp polls `GET /api/status?orderId=X` every 5s
- **Storage**: Cosmos DB status container with timeline array
- **Display**: Vertical stepper timeline, countdown timer, progress bar
- **Terminal states**: `completed` (green) or `expired` (red) — polling stops

## Original Project Reference

This plan extends the existing project at:
`C:\Users\mario.martins\Desktop\ITS-ICT\Cloud and Azure\AZURE\EventTrigger`

Current state: Bare-minimum Azure Functions Python v2 with a single EventGridTrigger that logs a warning. No real logic exists.
