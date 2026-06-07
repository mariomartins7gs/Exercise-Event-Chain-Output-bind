# ADR-004: Cosmos DB for Order State + Status Tracking

**Status**: Accepted  
**Context**: Need to persist order data (confirmed orders), status timeline (live tracking), and counter (increment).  
**Decision**: Use Cosmos DB with three containers: `Orders` (final documents), `OrderStatus` (timeline, polled by webapp), `Counter` (CAS counter).  
**Alternatives considered**: Single container for all (partition key collision risk), Table Storage for status (less flexible querying).  
**Consequences**: +Teaches Cosmos DB multi-container design, partition key strategy, free tier usage. Container separation keeps RU consumption predictable and RBAC scoped.
