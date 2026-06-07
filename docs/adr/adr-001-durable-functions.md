# ADR-001: Use Durable Functions for Orchestration

**Status**: Accepted  
**Context**: Need to coordinate a multi-step workflow with a 3-minute timeout and external event waiting.  
**Decision**: Use Durable Functions (orchestrator + activities) with `WaitForExternalEvent` + `CreateTimer` race pattern.  
**Alternatives considered**: Custom state machine with TimerTrigger polling a table (more code, less precise timeout, race conditions).  
**Consequences**: +Teaches canonical DF pattern, exact timeout, no race conditions, built-in checkpoint/replay. Requires DF extension and determinism discipline.
