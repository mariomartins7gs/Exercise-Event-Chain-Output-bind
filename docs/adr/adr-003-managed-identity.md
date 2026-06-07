# ADR-003: Managed Identity over Connection Strings

**Status**: Accepted  
**Context**: Function App needs to authenticate to Storage, Cosmos DB, ACS, and App Insights.  
**Decision**: Use System-assigned Managed Identity with RBAC role assignments.  
**Alternatives considered**: Connection strings (simpler but insecure, hard to rotate), Key Vault references (more setup).  
**Consequences**: +Teaches Entra ID + RBAC best practice, zero secrets to manage, automatic credential rotation. Requires each resource to have proper RBAC assignment in Bicep.
