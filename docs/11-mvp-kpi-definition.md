# 11 — MVP & KPI Definition

## MVP Gate: Minimum Viable Pipeline

The project reaches MVP when a student can **submit an order via the webapp and see it reach a terminal state (completed or expired)** with confirmation via SMS simulation.

### MVP Acceptance Criteria

| Criterion | Detail | Verification |
|-----------|--------|-------------|
| **A1** | Webapp serves from `$web` | `GET <url>/` returns index.html |
| **A2** | Order form POST succeeds | `POST /api/submit_order` returns 202 + `{orderId, displayOrder}` |
| **A3** | Blob is written to `orders-inbox` | Blob exists with matching `displayOrder` |
| **A4** | Orchestration starts and runs | DF instance transitions through states |
| **A5** | SMS payload is logged (simulated) | Log output contains `[SMS] To: <phone>, Order: ORD-XXXX` |
| **A6** | Confirm endpoint works | `POST /api/confirm_handler` raises event → status becomes `completed` |
| **A7** | Expiry works | No confirmation within 180s → status becomes `expired` |
| **A8** | Status polling returns data | `GET /api/status?orderId=X` returns timeline + secondsRemaining |
| **A9** | Webapp dashboard renders | Polling stops on terminal states, shows correct status |
| **A10** | Zero connection strings in config | All auth via Managed Identity |

## KPI Framework

KPIs are evaluated at **every phase** and tracked in `docs/02-tdd-test-plan.md`.

### Core KPIs

| KPI | Target | Measurement | Phase |
|-----|--------|-------------|-------|
| **T1 — Test Pass Rate** | 100% critical path | `pytest --tb=short` | Post-Code |
| **T2 — Line Coverage** | ≥80% overall | `pytest --cov=src` | Post-Code |
| **T3 — Module Coverage** | models:100%, counter:95%, activities:90%, orchestrator:95%, function_app:85% | `pytest --cov --cov-report=term-missing` | Post-Code |
| **T4 — Test Count** | ≥49 passing tests | `pytest --collect-only \| grep -c "TestCase"` | Post-Code |
| **T5 — Type Safety** | Zero mypy errors on `src/` | `mypy src/` | Post-Code |
| **T6 — IaC Validity** | Bicep compiles without warnings | `az bicep build --file infra/main.bicep` | Post-Infra |
| **T7 — Auth Surface** | Zero `AccountKey`/`connectionString` in code | `rg -n "AccountKey\|connectionString" src/` | Post-Code |
| **T8 — SMS Fallback** | Simulated mode works without ACS | `SMS_PROVIDER=simulated` env toggle test | Post-Code |
| **T9 — Determinism** | No `datetime.now()`, `random`, `uuid` in orchestrator | Code review / grep | Post-Code |

### Integrity Gates (Hard Blockers)

These must pass before considering the build healthy:

| Gate | Check | Fail Action |
|------|-------|-------------|
| G1 | All unit tests pass | Block merge |
| G2 | Coverage ≥80% | Block merge |
| G3 | No mypy errors | Block merge |
| G4 | Bicep builds | Block infra deploy |
| G5 | No connection strings | Block deploy |

## Baseline Record (Pre-Implementation)

| KPI | Value | Date |
|-----|-------|------|
| Test Pass Rate | 0% (no code) | — |
| Line Coverage | 0% | — |
| Test Count | 0 | — |

## Tracking

This document is updated after each implementation phase. Progress is recorded in `docs/02-tdd-test-plan.md`.
