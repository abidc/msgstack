# product-positioning

The one-pager and competitive framing PMM ships to prospects. Leads with the proof points from the message house, in the order the Q3 retro confirmed converts.

## Overview
Gets a skeptical engineer to yes on the usefulness test in under two minutes.

## Deprecations
- The pre-STRATEGY_V2 'organizational canon' one-pager is retired as of 2026-08-07. Do not resurrect its governance-platform framing, even for a compliance-minded prospect who asks for it by name. **[LOCKED]**

## Configuration Defaults
- One-pager CTA is the message house default ('Read the docs'), inherited rather than restated.

## Capabilities
- One-pager leads with the self-host proof point before the propagation one. Procurement objections ('does our data leave our network') kill deals faster than feature skepticism, so the answer has to land first. **[LOCKED]**

## Known Limitations
- The one-pager makes no enterprise-adoption claim. There are zero paying enterprise customers; every proof point stays scoped to self-hoster or homelab scale.

## Security Posture
- Self-hosted deploy means customer data and API keys never leave the customer's own infrastructure. An independent proof point from the self-host story, true by architecture — it doesn't require a formal security review to state. **[LOCKED]**

## Decisions
- We cut the enterprise RBAC / approval-workflow comparison table from the one-pager entirely. STRATEGY_V2 confirmed the governance apparatus isn't shipping, so a comparison table would be marketing a feature that doesn't exist.

## Audiences
### Sales-adjacent reader (there is no sales team)
Anyone forwarding the one-pager to a prospect without a call first.

**Q: A prospect asks about SOC2 or RBAC — what do I say?**
A: That the governance apparatus isn't shipping — STRATEGY_V2 cut it deliberately. Don't imply it's on the roadmap.

## Related Specs
- DEPENDS_ON → messaging-house
