# 10 — Spec-Driven Development (SDD) Workflow

## What is SDD?

Spec-Driven Development is a discipline where **written specifications precede every line of implementation code**. It bridges the gap between architecture design and TDD:

```
Architecture (WHAT) → Spec (HOW) → Tests (VERIFY) → Code (DO)
```

## SDD + TDD Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│  PHASE 1: SPEC                                                  │
│  Write a concise spec document for the module:                  │
│  • Contract (inputs / outputs / error states)                   │
│  • State machine (if applicable)                                │
│  • Edge cases + constraints                                     │
├──────────────────────────────────────────────────────────────┤
│  PHASE 2: TEST (TDD Red)                                       │
│  Translate spec into test cases:                                │
│  • Happy path                                                   │
│  • Each error/edge case from the spec                           │
│  • All tests fail initially (intentional)                       │
├──────────────────────────────────────────────────────────────┤
│  PHASE 3: CODE (TDD Green)                                     │
│  Write minimal implementation to pass tests:                    │
│  • No feature creep — only what the spec requires               │
│  • Refactor only after green                                    │
├──────────────────────────────────────────────────────────────┤
│  PHASE 4: VERIFY                                                │
│  • Run full test suite → 100% pass                              │
│  • Check coverage target                                        │
│  • Spec ↔ tests traceability matrix                             │
└──────────────────────────────────────────────────────────────┘
```

## SDD Document Template

Each module gets a lightweight spec before tests are written:

```markdown
## Module: `<name>`

### Contract
- **Input:** `<type, shape, constraints>`
- **Output:** `<type, shape>`
- **Side effects:** `<external calls, writes>`

### State Machine (if applicable)
```
state1 → event → state2
```

### Error States
| Condition | Error | Handling |
|-----------|-------|----------|
| ... | ... | ... |

### Edge Cases
- `...`
```

## Project Modules & Spec Status

| Module | Spec Written | Tests Written | Code Written |
|--------|-------------|---------------|-------------|
| `models.py` | ✅ (in docs/01) | ❌ | ❌ |
| `counter.py` | ✅ (in docs/08) | ❌ | ❌ |
| `activities.py` | ✅ (in docs/01, 03) | ❌ | ❌ |
| `orchestrator.py` | ✅ (in docs/01, 03) | ❌ | ❌ |
| `function_app.py` | ✅ (in docs/01, 03) | ❌ | ❌ |
| Webapp | ✅ (in docs/01, 09) | — | ❌ |
| Infra Bicep | ✅ (in docs/04) | — | ❌ |

## Benefits

- **Catch design flaws before writing code** — cheaper to fix a spec than refactor
- **Tests are derived from specs, not from code** — higher quality tests
- **Living documentation** — specs stay accurate because code follows them
- **Clear contract boundaries** — modules stay decoupled
