# launch-campaign

The MsgStack v2 launch campaign — creative, cadence and channel sequencing built on the message house and product-positioning specs.

## Constraints
- Campaign runs on owned channels only (LinkedIn, newsletter) for the first two weeks. No paid spend is approved until organic CTR is measured against the self-host-led creative variant.

## Deprecations
- The pre-STRATEGY_V2 'organizational canon' launch campaign draft is retired alongside the one-pager it was built from — 2026-08-07.

## Configuration Defaults
- Default cadence is two LinkedIn posts a week during the campaign window, routed through the existing content-desk judge/auto-post gate rather than a separate campaign queue.

## Dependencies
- Creative sequencing leads with the self-host proof point, same order as the one-pager — confirmed by the Q3 retro after the propagation-led variant underperformed. **[LOCKED]**

## Capabilities
- Hero creative is a recorded clip of editing a gateway-style threshold live and watching two downstream facts flip to 'outdated' — the propagation proof point, animated, because it's a mechanism nobody believes until they watch it move. **[LOCKED]**

## Decisions
- Campaign CTA matches the message house default ('Read the docs') rather than a lead-capture form — there's nowhere for a captured lead to go without a sales process.

## Audiences
### Growth marketer scheduling posts
Executes the campaign calendar.

**Q: Which proof point leads the first post?**
A: Self-host, always — the propagation demo is the second post, not the first. The Q3 retro is why.

## Related Specs
- DEPENDS_ON → messaging-house
- DEPENDS_ON → product-positioning
