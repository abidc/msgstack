# payments-api

Card and wallet payment capture for checkout. Owns the charge lifecycle and the public /v2/charges contract.

## Overview
The only service authorised to move money. Everything else proposes a charge; payments-api decides.

## Constraints
- Rate limit is 1000 requests/minute per API key, with a burst allowance of 1500 over any 10-second window. **[LOCKED]**

## Service Level Objectives
- p99 latency under 250ms and 99.95% monthly availability, measured at the gateway, excluding client-side network time. **[LOCKED]**

## Deprecations
- The v1 checkout endpoint is removed on 2027-01-31. v1 has been read-only since 2026-06-01; migrate to /v2/charges. **[LOCKED]**

## Configuration Defaults
- PAYMENTS_TIMEOUT_MS defaults to 8000. Raising it above 10000 exceeds the gateway's own timeout and produces 504s.

## Dependencies
- Requires auth-service >= 4.2 for token introspection. Versions below 4.2 do not return the scope claim and every request 403s.

## Known Limitations
- Partial refunds are not supported for wallet charges — only full reversal. Card charges support partial refunds.

## Security Posture
- PAN data never reaches application logs; the tokenisation proxy strips it before the request enters the service boundary. **[LOCKED]**

## Interface Contract
- POST /v2/charges is idempotent on the Idempotency-Key header. Replaying a key within 24h returns the original charge, not a new one. **[LOCKED]**

## Audiences
### Integrating engineer
Building a checkout flow against the public API.

**Q: Can I retry a failed charge safely?**
A: Yes — reuse the same Idempotency-Key. A replay within 24h returns the original charge rather than double-charging.

**Q: Why am I getting 403s after upgrading?**
A: auth-service below 4.2 omits the scope claim. Check its version first.

### On-call SRE
Paged against the payments error budget.

**Q: Charges are 504ing in bulk — where do I look?**
A: Compare PAYMENTS_TIMEOUT_MS against the gateway timeout. If it was raised above 10000 the gateway gives up first.

## Related Specs
- DEPENDS_ON → auth-service
- DEPENDS_ON → gateway-config
