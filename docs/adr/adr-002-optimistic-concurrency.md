# ADR-002: Cosmos DB Optimistic Concurrency for Auto-Increment Counter

**Status**: Accepted  
**Context**: Need atomic, sequential order IDs in a distributed environment with concurrent function instances.  
**Decision**: Use Cosmos DB ETag-based Compare-And-Swap with exponential backoff retry.  
**Alternatives considered**: Durable Entity counter (more abstract, adds conceptual overhead), Redis INCR (adds Azure Redis cost), SQL AUTO_INCREMENT (not serverless).  
**Consequences**: +Teaches optimistic concurrency, no extra services, CAS pattern is transferable knowledge. Requires understanding of ETags and conflict handling.
