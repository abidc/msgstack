# campaign-retro-q3

Retro on the Q3 test that compared a propagation-led launch variant against a self-host-led one.

## Known Limitations
- Sample size is one campaign week per variant. Treat the 40% figure as directional, not a benchmark to quote externally — that would itself violate the message house's claim-limit.

## Runbook
- Retro process: pull both variants' CTR from the campaign tracker, compare against the message house's proof-point ordering, and file any confirmed ordering as a locked assertion so it can't silently regress in the next campaign.

## Decisions
- Root cause of the propagation-led variant's underperformance: it opens with a mechanism demo before the reader has a reason to trust the mechanism matters. CTR was 40% lower than the self-host-led variant run the same week. Confirms lead-order should be a locked assertion, not a suggestion. **[LOCKED]**

## Related Specs
- INFORMS → launch-campaign
- INFORMS → messaging-house
