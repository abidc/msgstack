# checkout-web

Customer-facing checkout UI. Consumes payments-api and surfaces its limits and errors to end users.

## Dependencies
- Calls POST /v2/charges directly. Still contains a v1 fallback path that must be removed before the 2027-01-31 sunset.

## Capabilities
- Displays a rate-limit notice to the user when payments-api returns 429, quoting the 1000 req/min figure verbatim.

## Known Limitations
- The refund UI offers partial refunds for every payment method, including wallet — which payments-api rejects.

## Decisions
- We render errors client-side rather than server-side so the checkout shell stays cacheable at the edge. Revisit if SEO matters.

## Audiences
### Frontend engineer
Maintains the checkout flow.

**Q: What should a 429 show the user?**
A: The rate-limit notice quoting the current documented limit. Do not hardcode the number — it is a locked assertion in payments-api.

## Related Specs
- DEPENDS_ON → payments-api
