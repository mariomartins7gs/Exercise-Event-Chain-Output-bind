# ADR-005: Azure Communication Services for SMS

**Status**: Accepted  
**Context**: Need to send SMS confirmation messages to customers. Must be switchable between real and simulated for local dev.  
**Decision**: Use ACS SMS with free tier, with `SMS_PROVIDER` environment variable switching between `acs` (real) and `simulated` (log only).  
**Alternatives considered**: Twilio (external vendor, requires separate account), simulated only (less impressive for classroom).  
**Consequences**: +Teaches another Azure service, ACS free tier (200 SMS/mo) fits budget. Requires phone number provisioning and ACS endpoint configuration.
