# gateway-config

Edge routing, TLS termination and load shedding for all public traffic. Sets the limits every downstream service inherits.

## Constraints
- The gateway sheds load above 1200 requests/minute aggregate per upstream, returning 503 with Retry-After. **[LOCKED]**

## Service Level Objectives
- Gateway adds no more than 15ms p99 overhead to any upstream call.

## Configuration Defaults
- Upstream request timeout is 10000ms. This is the ceiling for every service behind the gateway; per-service timeouts must sit below it. **[LOCKED]**

## Security Posture
- TLS 1.2 is refused as of 2026-07-01. Clients must negotiate TLS 1.3. **[LOCKED]**

## Runbook
- To raise an upstream's shed threshold: edit tier config, apply to canary, watch 503 rate for 10 minutes, then roll to fleet.

## Audiences
### Platform engineer
Owns gateway configuration and tier assignment.

**Q: A service wants a higher rate limit — what has to change?**
A: The shed threshold here, not just the service's own limit. The gateway sheds first, so raising the service limit alone does nothing.

## Related Specs
- INFORMS → payments-api
