# auth-service

Token issuance and introspection. Every authenticated request in the platform resolves through it.

## Service Level Objectives
- Introspection responds in under 40ms p99. It sits in the request path of every other service, so its budget is the tightest. **[LOCKED]**

## Configuration Defaults
- Access tokens live 3600s, refresh tokens 30 days.

## Security Posture
- Signing keys rotate every 90 days with a 7-day overlap window during which both the old and new key validate. **[LOCKED]**

## Interface Contract
- POST /introspect returns active=false rather than 401 for an expired token. Callers must check the body, not just the status. **[LOCKED]**

## Version Policy
- Minor versions are backward compatible within a major. The scope claim was added in 4.2 and is required by downstream services. **[LOCKED]**

## Audiences
### Integrating engineer
Consuming tokens from another service.

**Q: Why does an expired token return 200?**
A: By design — check active=false in the body. A 401 means the introspection call itself was unauthorised, not the token.
