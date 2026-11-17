# MsgStack v3 — the brand-voice layer for small-business marketing

**Status:** PROPOSAL, 2026-11-16. Nothing in this document is live. It needs the decisions in §12 before any of it ships; the vertical slice in `src/marketing/` is behind the same PR so the proposal can be tried, not just read.
**Inputs:** the Track 5 market research of 2026-11-16 (cited below as *Research §n*, with its own sources named), `PRODUCT_SPEC.md` 0.8.4, `docs/archive/STRATEGY_V2.md`, `docs/COMPETITIVE_ANALYSIS.md`, the live site (`msgstack-website/src/app/pricing/page.tsx`), and a read-only inventory of Syd's content desk, voice-lint, Belay and the listmonk newsletter (`docs/MVP_SPEC.md` §7 has the table).
**Supersedes:** the "organizational canon layer for enterprise AI grounding" positioning in `README.md` / `PRODUCT_SPEC.md` **if adopted**. Until then those remain current.

---

## 1. The honest starting point

MsgStack today is an Apache-2.0 MCP server plus admin UI with one genuinely differentiated idea, **Tier-1 locked claims reproduced verbatim or not at all, with approval state and an alignment score**, wrapped in enterprise product-marketing vocabulary (canon domains, DRIs, SLAs, RBAC, CI/CD promotion). Three facts constrain what comes next:

1. **The governance apparatus has never been used.** `STRATEGY_V2.md` §1 counted one row across `users`, `element_permissions`, `artifact_entry_bindings`, `temporary_canon_overlays`, `query_audit_log`, `snapshots` and `review_logs` after a year. That is the day-job (ServiceNow Nucleus) overlap, built because it felt necessary.
2. **This would be the third positioning in fifteen months** (PMM canon → engineering memory layer, Aug 2026 → PMM canon again, Oct 2026). Another pivot without kill criteria is the real risk, not the market.
3. **The site promises "no hosted product and no paid tier"** (`/pricing`, verbatim) and lists "a paid tier or freemium product" under *What it isn't*. Any revenue plan must first retire that promise honestly.

The research verdict stands and this document adopts it: **"marketing OS" is hype for MsgStack today** (Research §3: an OS claim needs the system of record *and* execution for at least one channel; MsgStack has the brand record and nothing in activation or measurement), and **MCP-only is a liability** for the end small business (Research §4: owners live in the ChatGPT app, Canva and Mailchimp; connector setup is a hard stop for the 56% with an hour a day; no agent-native entrant ships MCP-only).

## 2. Positioning

### The claim

> **MsgStack is the brand-voice layer your AI tools check before anything ships.** Put your voice, your claims and your no-go list in once. Every draft, from Claude, ChatGPT, Buffer or your agency's intern, gets checked against it, queued for your yes, and logged when it goes out.

Not "a marketing OS". Not "AI CMO". The staffing metaphor ("AI marketing team") is what the agent-native cohort uses (Research §2) and is crowded at $39–$129; the governance metaphor ("the layer they all check") is empty and is exactly what MsgStack's engine already does. If Abid wants an OS word for SEO, qualify it: *"the brand OS your agents run on"*, and only once the shipped-content log exists so there is a record of what went out.

### Why this is defensible

- None of the MCP servers SMBs can already attach (Buffer, Canva, Mailchimp, Klaviyo, Meta Ads, HubSpot, Zapier, Notion) owns *approved claims*; every one will publish whatever the model drafts (Research §4, "Where MCP-first is a real advantage" point 3).
- Verbatim-tier generation is a live research problem (ACM 2026 "Policy-Guided RAG", arXiv "EvidenT") and no commercial competitor ships it as a per-entry feature (`docs/COMPETITIVE_ANALYSIS.md`). Adobe Brand Intelligence and Jasper Brand IQ detect drift after the fact; MsgStack prevents it by construction.
- The agent-native cohort prompts the model with a brand profile and differentiates on autonomy level (Research §2 pattern). A deterministic gate plus a stored decision trail is additive to all of them, not a competitor.

### What the words become

| Today (enterprise PMM) | v3 (small business) | Why |
|---|---|---|
| Canon domain | **Brand** | It is the tenant and the thing an agency bills by |
| Canon entry, Tier 1 locked | **Locked claim** (verbatim or absent) | Same mechanism, plain name |
| Brand voice / word_list entries, AudienceProfile | **Voice canon** (tone, we say / we never say, off-limits, CTA, examples) | One object the owner can fill in ten minutes |
| Alignment scoring (LLM) | **Voice gate** (deterministic first, LLM judge second) | Cheap, explainable, quotes the span at fault |
| Approval lifecycle on entries | **Approval queue on drafts** | The decision point moves from the canon to the content |
| Query audit log | **Shipped-content log** | A record the owner actually opens |
| DRI, SLA, RBAC, CI/CD promotion, sub-canon inheritance | retired from the pitch (code may stay) | Zero rows; Nucleus overlap |

## 3. Segments: agree with the ranking, change the sequencing

The research ranks (1) boutique agencies / fractional CMOs, (2) solo coaches and consultants, (3) Shopify DTC micro-brands (Research §5). I agree with the ranking **as a revenue order** and disagree with it **as a build order**.

| # | Segment | Size (Research §5, sources there) | WTP | Core jobs to be done | Role in the plan |
|---|---|---|---|---|---|
| 1 | Boutique agencies, freelancers, fractional CMOs serving SMBs | ~100,200 US digital agencies, ~114,000 ad agencies (IBISWorld 2026); 322–342k marketing consultants; mostly 1–10 people | $99–$499/mo normal (GHL $97/297/497; Sendible white label from $349; Vendasta $99/$499) | Keep 5–50 clients' claims, voice and no-go lists straight across juniors and tools; prove to the client that nothing off-brand shipped; bill per brand | **First revenue.** Already pays per brand/workspace (Metricool $20 for 5 brands, Planable $33–49/workspace), already lives in Claude/ChatGPT, has a compliance pain with a dollar value |
| 2 | Solo coaches, consultants, expert-led B2B services | ICF ~110,500 active coaches worldwide (2025); Marketdata 232k US (modelled, high) | $29–$79/mo, high churn, DIY | Sound like themselves across LinkedIn, newsletter and proposals; post consistently without it becoming a second job; never ship a claim they cannot back | **Proof and dogfood.** Abid is in it (The Climb, the newsletter). Zero CAC for the first ten users. Low ACV, so it is the credibility segment, not the revenue one |
| 3 | Shopify DTC micro-brands (<$1M) | Shopify FY2025 GMV $378B; merchant count not disclosed in reliable sources | $30–$100/mo at the micro end | Identical ingredient / health / price claims across email, social, ads and PDPs; Klaviyo + Meta + Canva already MCP-complete | **Deferred to Q2 2027, served through segment 1.** Shopify Sidekick is the incumbent agent in every admin; App Store distribution is expensive; Katia's accounts give one real test brand before then |

Not pursued: local service businesses. They buy outcomes (reviews, missed-call texts, bookings), are owned by Thryv/Podium/Birdeye/GHL at $99–$599 on annual contracts, and are reached through agencies (Research §5).

**Sequencing argument.** The product is proven on Abid's own three brands first (The Climb on LinkedIn, *Notes from the Machine* on listmonk, Katia's Instagram) because that is the only place where the full loop (draft → gate → yes → ship → read back) can be run weekly with no sales cycle and real stakes. The first paying customers are agencies because they already pay per brand and because every agency is a channel into segments 2 and 3. That is also why the data model is multi-tenant from the first commit, not retrofitted.

## 4. Own vs integrate

The rule: **own the record and the decision; rent the send.**

| Layer (Research §3 table) | Own | Integrate (over their MCP / API) | Never build |
|---|---|---|---|
| System of record | Brand, voice canon (versioned), locked claims, content items, approvals, schedule records, shipped log | Source docs via Drive/Notion ingestion (existing) | A CMS |
| Workflow | Intake → draft → gate → approve/reject → schedule record → shipped | Publishing: **Buffer MCP** (all plans, May 2026) for social; **listmonk** (own) / **Mailchimp** connector / **Klaviyo MCP** for email; LinkedIn via n8n or Buffer; Meta Ads MCP (beta) later | A scheduler; an ESP |
| Data | Nothing customer-level | HubSpot MCP (CRM read/write; marketing objects read-only), Shopify | A CRM |
| Governance | Voice gate (deterministic rules + optional LLM judge), locked-claim verbatim check, approval with reasons, override trail, per-brand autonomy tier, quota | — | Enterprise RBAC/SSO (until an agency with >10 seats asks and pays) |
| Agents | Week generator, one-shot rewriter, weekly digest composer, results reader | Canva AI Connector for design (all plans incl. Free); the client's own Claude/ChatGPT as the orchestrator | Image/deck rendering (park Fabric.js / reveal.js / Penpot streams) |
| Activation | The *schedule record* and the handoff recipe | Buffer, listmonk/Resend, Mailchimp, LinkedIn, Meta | Direct OAuth to every network |
| Measurement | Shipped log + metrics columns; weekly "what went out and was it on-canon" report | Buffer analytics, listmonk/Resend delivery, li-metrics-style scrapes, GA4 | Analytics product |

What changes versus `ROADMAP.md` ("What We're Not Building: a full CMS or editorial calendar; a social media scheduling tool"): we still build neither a scheduler nor a calendar *product*; we **do** keep a schedule record and a shipped-content log, because without them the system-of-record claim collapses (Research §4 liability 3).

## 5. Data model

Implemented in `src/marketing/models.py` + `store.py` (tables prefixed `mkt_`, separate declarative base so the 4,000-line `src/store.py` migration history is untouched).

```
Workspace (existing: id, slug, api keys, token budget)           # the paying account
  └─ Brand            (id, workspace_id, name, owner, kind, autonomy, weekly_quota{channel:n})
       ├─ VoiceCanon  (brand_id, version, one_liner, audience, tone[], we_say[], we_never_say[],
       │               locked_claims[], topics[], off_limits[], cta, example_posts[],
       │               max_words{channel:n}, allow_first_person_experience)   # immutable versions
       ├─ ContentItem (brand_id, canon_version, channel, slot_date, topic, body,
       │               status: draft|needs_rework|approved|rejected|published|failed,
       │               gate{ok, clean, violations[{rule, severity, message, span}]},
       │               generated_by, rewrite_count)
       ├─ Approval    (content_id, decision approve|reject, reason, decided_by, override_hard)
       ├─ Schedule    (content_id, channel, publish_at, destination, status, external_ref)
       └─ ResultRecord(content_id, channel, published_at, external_ref, metrics{})
```

Design points:
- **Brand is the tenant key.** Every read of a child row is `brand_id`-checked in the store (`NotFound` on a cross-brand id). Workspace is the billing unit above it: one agency, many brands.
- **Canon versions are append-only**; every ContentItem records the `canon_version` it was gated against, so a later canon change never silently re-labels old content.
- **Audience/segments** are a field on the canon (one reader), not a table, until a brand has more than one audience that changes the copy. `AudienceProfile` (existing, workspace-scoped) is the upgrade path.
- **Campaigns** are deliberately absent in the slice: a "campaign" for these segments is a topic plus a date range. Add a `campaign_id` column on ContentItem when a brand asks for grouped reporting; do not model it first.
- **Existing core tables are not replaced.** A Brand can later point at a CanonDomain (`canon_domain_id` nullable FK) so an agency that wants the full typed graph for a client gets it as an upgrade rather than a different product.

## 6. Agent layer

Borrowed from Syd, with the evidence that earned each rule:

| Runs without asking | Needs a human yes | Evidence |
|---|---|---|
| Drafting a week per channel against the canon | Anything that publishes or schedules | Syd autopilot (10/15–10/24): automated posts drew 150–450 impressions against 1k–23k for Abid's own; he switched autopilot off. **Stage-for-yes is the default tier**, not a safety setting |
| Deterministic voice gate on every draft; hard violations block | Overriding a hard violation (requires a reason, recorded) | voice-lint history: eight publishing paths were linted only after a self-comment path published unlinted; the gate must sit in the path, not beside it |
| One automatic rewrite, keep the better version | A second rewrite or a manual edit (edits are re-gated) | Content desk autopilot rule (one rewrite, keep the better); the judge's real posts mostly scored "hold", so the model is conservative by design |
| Weekly quota per channel (Plan Gate) | Raising the quota | Plan Gate (3 articles + 1 card per account per month) exists because 5 articles/week was "too much" and 33 pending / 81 expired drafts followed |
| Weekly digest of the queue (one message, buttons) | Every decision in it | Notification diet: 18 → 8 Telegram messages/day; digest batching to 08:30 |
| Reading back what shipped and attaching metrics | — | 8 of Abid's "Post it" decisions once posted nothing (n8n `httpMethod` bug); a schedule record plus a results readback is how that is caught |

**Autonomy ladder per brand** (`Brand.autonomy`): `approve_each` (default, the only tier implemented in the slice) → `auto_schedule_clean` (gate-clean drafts go straight to the schedule record, digest afterwards; offered only after ≥15 human decisions with ≥90% agreement between the gate's verdict and the owner's, Syd's `agreement()` rule) → `autopilot` (never default; agency-only; kill switch per brand). Deny rules (off-limits topics) override every tier.

**LLM judge.** Not in the slice. The deterministic gate catches shape and truth violations; a rubric judge (Syd's `judge` pool pattern, calibrated on the brand's own kept/killed labels) is the Phase 2 upgrade once there are ≥30 labelled decisions per brand to calibrate against. Shipping the judge first would repeat the content-desk lesson that a judge alone cannot fix generic content.

## 7. Architecture: how the MCP server grows into it

```
                 Claude / ChatGPT / Cursor / n8n / agency's own agent
                                   │  MCP (streamable-http, OAuth 2.1 for the directories)
   ┌───────────────────────────────▼─────────────────────────────┐
   │ MsgStack hosted (multi-tenant)        thin web UI (owner)   │
   │  brand_intake · update_voice_canon · check_voice            │  queue · canon editor ·
   │  generate_week · review_queue · approve/reject              │  week view · shipped log
   │  mark_published · get_results           REST /api/marketing │
   │  (existing: search_canon, generate_artifact, graph...)      │
   └──────────────┬───────────────────────────┬──────────────────┘
                  │ Postgres (brand-scoped)    │ handoff recipes
                  ▼                            ▼
          brands · canons · items ·     Buffer MCP · listmonk/Resend · Mailchimp ·
          approvals · schedules ·       Klaviyo · LinkedIn (n8n) · Canva connector
          results
```

1. **Same server, new tool family.** The eleven marketing tools sit beside the existing canon tools in `src/server.py`; one `PathRouter`, one DB. Self-hosters get everything, free, as today.
2. **Hosted multi-tenant** = the same image on the Hetzner VPS behind Traefik with Postgres, using Belay's `deploy/ship.sh` pattern (build here, stream images over SSH, `:prev` tag rollback). Workspace = paying account (existing `WorkspaceModel` + `ApiKeyModel` scopes); Brand = tenant row. Per-tenant export (`GET /api/marketing/brands/{id}/export`) is the lock-in antidote and the GDPR answer.
3. **OAuth 2.1 on `/mcp`** is required before any directory listing (Claude and ChatGPT both require OAuth for remote servers; API keys alone keep it a developer tool). This is the single largest piece of new infrastructure in the plan and is scheduled in Phase 2.
4. **Thin UI first as three pages in the existing admin** (LEDGER skin): Queue (approve/reject with reason, edited body), Canon (the ten intake fields, version history), Week/Log (schedule records and shipped items). A separate owner-facing app only when an agency's client needs a login that is not the agency's.
5. **Publishing is a recipe, not an integration**, in Phase 1: the owner's Claude session calls `approve_content`, then Buffer's `create_post` with the approved body, then `mark_published` with Buffer's id. Phase 3 adds a `destination=buffer` worker that does those two calls server-side.

## 8. Multi-tenancy

- Workspace → brands → content; `brand_id` on every child row; store-level checks (implemented and tested: `test_cross_brand_access_is_refused`).
- API keys already carry workspace and scopes; marketing tools must honour `workspace_id` from the key when `MSGSTACK_AUTH_ENABLED=true` (slice gap, Phase 2 item: today `brand_intake` accepts `workspace_id` as a parameter).
- One Postgres, row-scoped. Not one DB per tenant: at 5–50 brands per agency and tens of agencies that is operationally wrong, and SQLite stays the default for self-host.
- LLM spend metered per workspace with the existing `TokenUsageModel` and `max_token_budget` (402 on exhaustion already exists in `web_app.py`). Soft cap, not the bill (Research §6.1: 78% of IT leaders hit unexpected consumption charges; owners want flat).

## 9. Pricing and packaging

Per brand, unlimited seats, flat monthly, smooth overage, open-core. Consistent with Research §6 (per-brand beats per-seat for anything an agency touches; agent-native cohort clusters at $39–$129 flat; agency/white-label is a distinct tier at $199–$299; cliffs are where SMBs churn).

| Tier | Price | Brands | Includes | Who |
|---|---|---|---|---|
| **Self-host** | $0, Apache-2.0 | unlimited | Everything, your keys, your box | Builders, the funnel |
| **Hosted Free** | $0 | 1 | Intake, gate, queue, 10 generated drafts/mo, community support | Trial |
| **Solo** | **$39/mo** ($390/yr) | 2 | Unlimited gate checks, 60 drafts/mo, digest, Buffer/listmonk recipes, directory connector | Segment 2 |
| **Studio** | **$99/mo** | 5 | + LLM judge, weekly on-canon report, Drive/Notion ingestion, API | Fractional CMOs, small agencies |
| **Agency** | **$249/mo** | 15 | + client approval link per brand, white-label report, autonomy tier 2, priority support | Segment 1 |
| Overage | $12/brand/mo | | | smooth, no tier jump |

Positioning check: Solo sits inside the $50–$100/mo typical SMB stack (Research §1) only if it replaces something; it replaces the "paste my brand doc into ChatGPT again" tax, not a tool, so expect it to be the volume tier with churn. Agency is where margin lives. Do **not** meter LLM calls as the bill; cap drafts/month per tier and sell overage per brand.

What must change first: the `/pricing` page copy ("no hosted product and no paid tier"). The draft PR on `msgstack-website` does that honestly: OSS stays free forever; hosting, connectors and support are paid.

## 10. Onboarding wedge: the ten-minute intake

Eight questions, answered in any order, in a chat (`brand_intake` then `update_voice_canon`) or on one form (`POST /api/marketing/brands`). The tool returns completeness and the next three questions, so the client's own assistant can run it:

1. In one sentence: what do you do, and for whom?
2. Who exactly reads this? One person, not a market.
3. Three to five words for how you want to sound (and one for how you never want to sound).
4. Words or phrases you never want to see in your copy.
5. Any claim, number, price or tagline that must appear exactly as written or not at all.
6. Three to six topics you want to be known for.
7. What should a reader do next, in your words?
8. Paste one to three things you wrote yourself that sound like you.

Then `generate_week` for one channel produces the first gated drafts, and the first `approve_content` creates the first schedule record. Time-to-first-queue is the activation metric. Belay's intake engine pattern (spec + typed draft + missing-fields function + merge, `worker/belay_worker/agents/prep/engine.py`) is the reference if this becomes a multi-turn agent rather than a form.

## 11. What to kill, park, and keep

**Kill (remove from the pitch and the site; code may stay until it costs something):**
1. The "no paid tier, ever" promise. Replace with open-core.
2. "Organizational canon layer for enterprise AI grounding" as the headline, and the vocabulary that comes with it (DRI, SLA, RBAC, CI/CD promotion, sub-canon inheritance policies). One row in a year.
3. `engineering_spec` and `policy_shield` as public roadmap items. They are the Nucleus overlap re-entering through the side door, and no SMB buys them.
4. The homepage stat row ("100% deterministic", "0 drift shipped", "<1ms"): STRATEGY_V2 §8 called for an honest-claims audit and it never happened. A truth product cannot carry unverifiable numbers.
5. "Marketing OS" as the headline claim (see §2).

**Park (keep the code, stop investing):** the visual artifact engine (Fabric.js canvas, reveal.js decks, Penpot export; Canva's connector on all plans does this better), competitive-intel capture and battlecards (PMM), the Slack/Teams agent as the *primary* surface (keep as an agency feature later), Google Drive sync beyond ingestion.

**Keep and rename:** locked claims (Tier 1), approval states, alignment scoring (as the LLM judge behind the deterministic gate), AudienceProfile (as the multi-audience upgrade), workspaces and API keys, OpenRouter routing, the graph (as the agency "typed claims across 15 brands" upgrade, not the wedge).

**Kill criterion for the whole plan:** the 90-day roadmap ends with either ≥$1,000 MRR from ≥5 brands that are not Abid's, or a written park decision. No fourth positioning without that evidence.

## 12. Decisions only Abid can make

Recommendation in one line each; detail in `ROADMAP_90_DAYS.md` §0.

1. **Adopt this positioning (brand-voice layer, SMB) or stay enterprise-PMM?** Adopt, with the §11 kill criterion written into the roadmap.
2. **Keep the name MsgStack?** Keep: the domain, GitHub stars and `mcp.abidc.dev` are sunk assets; the hosted product can be "MsgStack for brands" without a rename.
3. **Hosted + paid (open-core) or OSS-only?** Open-core: Apache-2.0 core unchanged; hosting, OAuth connectors, judge and reports are the paid product.
4. **Pricing ladder** ($0 / $39 / $99 / $249 per brand-tier, $12 overage): accept as the opening ladder; revisit after five paying brands.
5. **First paying segment:** agencies and fractional CMOs; solo operators as the proof and funnel; DTC deferred.
6. **What to kill now** (§11 list 1–5): approve the list, especially the `/pricing` promise and the stat row.
7. **Dogfood scope:** The Climb (LinkedIn) and the newsletter (listmonk) from week 1; Katia's Instagram only with her yes.
8. **Autonomy default:** `approve_each` for every brand, tier 2 earned at ≥15 decisions / ≥90% agreement, autopilot never default.
9. **Build the thin UI inside the existing admin (LEDGER) or as a new app?** Inside the admin for 90 days.
10. **Hosting location:** Hetzner VPS alongside Belay (survives a home outage), not the ThinkPad tunnel.
