# 90-day roadmap — MsgStack brand-voice layer

**Window:** Mon 2026-11-17 → Sun 2027-02-14 (13 weeks). **Status:** PROPOSAL; starts only after the §0 decisions. Companion to `STRATEGY_V3_MARKETING_OS.md` and `MVP_SPEC.md`. Weeks are calendar weeks; "exit" means every criterion is met with evidence linked in the repo, not a feeling.

## 0. Gate (before week 1)

Abid decides the ten items in `STRATEGY_V3_MARKETING_OS.md` §12. Minimum to start Phase 1: decisions 1, 3, 7 and 8. Without 1 and 3 this is a dogfood toy, and that is fine, but then Phases 2–3 do not run.

## Phase 1 — Prove it on our own brands (weeks 1–4, Nov 17 – Dec 14)

Goal: the full loop (intake → week of drafts → gate → yes/no → schedule record → shipped → read back) runs every week on Abid's real channels, from Claude Desktop, with no new UI.

| Week | Milestone | Done when |
|---|---|---|
| 1 (Nov 17) | PR `feat/marketing-os-slice` reviewed and merged; container rebuilt with the eleven marketing tools live on `mcp.abidc.dev`; The Climb brand created from `seed_data/brand_intake_example.json` **after Abid edits every placeholder**; first `generate_week(linkedin)` reviewed in Claude Desktop | 3 LinkedIn drafts approved or rejected with reasons; `get_results` shows what shipped |
| 2 (Nov 24) | *Notes from the Machine* brand (channel `newsletter`, destination `listmonk`); a `newsletter` draft goes through the queue and is sent via the existing listmonk flow (read `claude-context/newsletter.md` first: rate limits, 100/day cap); `mark_published` with the campaign id | 1 newsletter section shipped through the queue; locked claims list for the newsletter agreed |
| 3 (Dec 1) | Katia's Instagram brand (only with her yes); Buffer MCP handoff recipe documented and used once (`approve_content` → Buffer `create_post` → `mark_published`); weekly digest: a Syd-style one-message queue summary (reuse `digest.py` pattern; may live in Syd for now) | 3 brands, 3 channels, ≥1 item each shipped via the queue; recipe in `docs/` |
| 4 (Dec 8) | Review the first 4 weeks of decisions: approval rate, edit reasons, gate false positives (soft rules that owners always override) and false negatives (things that shipped and should not have); tune rules; freeze the data model | Written review in `docs/dogfood/2026-12.md`; gate rule changes with tests |

**Exit criteria (all):**
- 4 consecutive weeks in which every item published on the three brands went through the queue (no side-door posts).
- Zero items shipped with a fabricated number or a paraphrased locked claim (`get_results` `gate_clean`/override audit).
- ≥60% of generated drafts approved without edit, or every edit carries a reason that maps to a gate rule or a canon field (so the canon can learn).
- Median time from `generate_week` to a decision < 24 h (the content-desk failure was Abid forgetting to review; if this misses, the digest and quota are wrong, not the users).
- No change to `src/store.py` migrations required by the slice.

## Phase 2 — Hosted, paid, and findable (weeks 5–8, Dec 15 – Jan 11; holiday-adjusted)

Goal: a stranger can sign up, run the ten-minute intake in Claude or ChatGPT or the thin UI, and pay. Five design partners on a founding price.

| Week | Milestone | Done when |
|---|---|---|
| 5 (Dec 15) | Thin UI inside the LEDGER admin: Queue page (approve/reject/edit with reason), Canon page (eight fields + versions), Week/Log page (schedule records, shipped) | Abid runs week 5's decisions in the UI, not Claude; UI smoke test in CI |
| 6 (Dec 22) | Hosted deployment on the Hetzner VPS: Postgres, Traefik host, Belay-style `ship.sh`, nightly `pg_dump` into the existing `backup-moved-sites.sh`, Kuma monitor; workspace-scoped auth enforced on marketing tools (`MSGSTACK_AUTH_ENABLED=true`); per-brand export endpoint | `app.msgstack.ai` (or chosen host) serves the UI + `/mcp`; restore drill from a dump passes |
| 7 (Dec 29) | OAuth 2.1 on `/mcp` (authorization server + dynamic client registration as the directories require); submit to the Claude connector directory and the ChatGPT plugin directory; Stripe billing generalised from Belay (`web/src/stripe/webhooks.ts` pattern: price→tier table, workspace id in metadata, portal session, entitlement check, tests) | OAuth flow works from Claude Desktop and ChatGPT dev mode; test-mode checkout → workspace tier flips |
| 8 (Jan 5) | Website: `/pricing` rewritten (the draft PR), homepage headline and stat row replaced, "built for Claude/ChatGPT" page; outreach to design partners (2 agencies, 3 solo) at a founding price ($19 Solo / $99 Agency for 12 months) | 5 design-partner brands created by people who are not Abid; ≥2 paid (test or live) |

**Exit criteria (all):**
- 5 brands owned by others live on the hosted instance; ≥2 paying.
- OAuth connector listed or formally submitted to at least one directory.
- Tenant isolation test suite green on Postgres as well as SQLite; one attempted cross-tenant read in logs returns 404 (deliberate probe).
- Time-to-first-queue (sign-up → first draft in queue) under 15 minutes for 3 of 5 partners, measured.
- `/pricing` no longer says "no paid tier".

## Phase 3 — Agency tier and the loop closing itself (weeks 9–13, Jan 12 – Feb 14)

Goal: an agency can run 5–15 client brands, show each client an on-canon report, and the product reads back results without a human copying ids.

| Week | Milestone | Done when |
|---|---|---|
| 9 (Jan 12) | Client approval link per brand (token URL, no login; approve/reject with reason) and a per-brand weekly on-canon report (what shipped, gate status, overrides) | One agency partner's client approves via the link; report emailed via Resend |
| 10 (Jan 19) | `destination=buffer` worker: approved items are posted to Buffer server-side at `publish_at`, `external_ref` filled, status moves to published; same for `listmonk` tx/campaign creation | ≥10 items shipped by the worker across partners with zero manual `mark_published` |
| 11 (Jan 26) | Results ingestion: Buffer analytics and listmonk/Resend delivery pulled into `ResultRecord.metrics` nightly; LLM judge (Syd `judge` pattern) behind the deterministic gate, calibrated per brand on the labels collected since week 1, dark-launched (scores recorded, not enforced) | metrics on ≥80% of shipped items; judge agreement with owners measured |
| 12 (Feb 2) | Autonomy tier 2 (`auto_schedule_clean`) offered to brands with ≥15 decisions and ≥90% agreement; kill switch and deny rules tested; `weekly_quota` editable in UI | ≥1 brand opts in and runs a week without an incident |
| 13 (Feb 9) | Retrospective and decision: MRR, churn, support load, LLM cost per brand; write `docs/decisions/2027-02-continue-or-park.md` | The §11 kill criterion is evaluated in writing |

**Exit criteria:**
- ≥$1,000 MRR from ≥5 brands not owned by Abid, **or** a written park decision. No third option.
- LLM cost per active brand per month under 15% of its tier price, measured from `TokenUsageModel`.
- Every published item for every brand has a Schedule row and a ResultRecord row (no orphan publishes).
- Zero hard-violation items shipped without a recorded override.

## Standing rules for the 90 days

- Branch + PR per change, merged after review, rebuilt after merge (merged is not live). Never deploy from a feature branch.
- Any claim that goes on the website must be backed by a test or a measurement in this repo (the honest-claims rule from STRATEGY_V2 §8, this time enforced in PR review).
- No new positioning documents until the week-13 decision.
- Secrets never in the repo; the hosted `.env` lives on the VPS as Belay's does.

## Explicitly not in these 90 days

Shopify/DTC listing, Meta Ads activation, the visual artifact engine, Slack/Teams as a primary surface, SSO/RBAC, Neo4j, a native mobile app, campaigns as a first-class object, any rename of the project.
