# MVP spec — the thin vertical slice, and what the first paying customer needs

**Status:** the slice in §1–§5 is BUILT on branch `feat/marketing-os-slice` (`src/marketing/`, 39 tests). §6 lists what is still required before anyone pays. §7 is the reuse inventory this slice and the roadmap draw on.

## 1. The slice in one paragraph

A brand owner (or their agent in Claude/ChatGPT) answers eight intake questions → MsgStack stores a versioned **voice canon** for that **brand** → `generate_week` writes up to N drafts for one channel for one week, each run through a **deterministic voice gate** that quotes every violation and blocks hard ones (fabricated numbers, paraphrased locked claims, banned phrases, off-limits topics, invented first-hand experience) → drafts sit in a **review queue** → a human **approves** (creating a **schedule record**) or **rejects with a reason** → when it ships, `mark_published` records it → `get_results` reads back what went out, who approved it, whether anything was overridden, and any metrics. Nothing in the slice publishes anywhere.

## 2. Tools (MCP, `src/server.py`) and routes (REST, `src/marketing/api.py`)

| MCP tool | REST | Purpose | Autonomy |
|---|---|---|---|
| `brand_intake` | `POST /api/marketing/brands` | Create brand + canon v1 from partial answers; returns `missing` and `next_questions` | agent |
| `update_voice_canon` | `PATCH /api/marketing/brands/{id}/canon` | Append canon version (lists replace) | agent; locked-claim changes should be owner-confirmed in the UI (Phase 2) |
| `get_brand`, `list_brands` | `GET /brands/{id}`, `GET /brands` | Read | agent |
| `check_voice` | `POST /brands/{id}/check` | Gate any text (kind `post` or `comment`, with `source_text` brief) | agent |
| `generate_week` | `POST /brands/{id}/generate` | N gated drafts for one channel/week; one rewrite on violations; quota-capped; template mode without a key | agent |
| `review_queue` | `GET /brands/{id}/queue` | Open items (draft + needs_rework) or by status | agent |
| `approve_content` | `POST /brands/{id}/content/{cid}/approve` | Human yes → Approval + Schedule; refuses hard violations unless `override` + reason; `edited_body` is re-gated | **human** |
| `reject_content` | `.../reject` | Human no, reason required | **human** |
| `mark_published` | `.../published` | Shipped: external ref, time, metrics → ResultRecord | agent (after the real send) |
| `get_results` | `GET /brands/{id}/results` | Shipped log + still-scheduled | agent |

Errors: unknown brand or cross-brand id → `NotFound` (404); bad input → `ValueError` (400). MCP wrappers surface those as tool errors.

## 3. Voice gate rules (`src/marketing/voice_gate.py`, version `2026-11-16.1`)

Ported from `C:\Users\Abid\voice-lint\lint_template.js` (Abid's own code; no third-party license involved), generalised:

| Severity | Rules | Source |
|---|---|---|
| **Hard** (block approval) | `empty`, `fabricated-number` (any figure not in the brief or canon; single digits exempt), `locked-claim-paraphrase` (a locked claim's number appears but the claim text does not), `fabricated-experience` (unless the canon allows first-person experience), `banned-phrase` (`we_never_say`), `off-limits-topic` | truth + brand |
| **Soft** (shown to approver) | `em-dash`, `en-dash`, `antithesis` (4 shapes), `staccato`, `hook-colon`, `rule-of-three`, `agreement-opener`, `filler`, `instruction-leak`, `maxim-until`, `maxim-parallel`, `formula-hedge`, `formula-superlative`, `formula-most`, `formula-isjust`, `formula-without`, `formula-whatreally`, `too-long` (per-channel budget, canon override), `missing-cta` (long-form only) | shape |
| **Comment-only** (soft, `kind="comment"`) | `familiarity`, `verdict`, `third-party-congrats`, `inflation`, `borrowed-phrase` | replying to strangers |

Not ported as universals (one person's stance, not a quality signal): the layoff/workforce block and "prescribing to leaders". A brand puts those words in `off_limits`. The rewrite prompt (`rewrite_prompt`) describes requirements and never demonstrates them with a pasteable phrase, per the instruction-leak lesson in `project_voice_system.md`.

## 4. Generation (`src/marketing/generator.py`)

- LLM path through the repo's `llm_client()` (OpenRouter), model `gpt-4o-mini` by default; system prompt carries the canon, lists locked claims as "reproduce exactly or omit", and gives example posts as register references "not templates".
- One rewrite on any violation; the better version (fewer hard, then fewer total) is kept. A failed rewrite never loses the original.
- Template path when no key is configured or `use_llm=False`: honest scaffolds from canon text, marked `generated_by="template"`, so the loop runs in CI and in a demo without secrets.
- Slots follow the channel's default posting days (LinkedIn Mon/Wed/Fri, newsletter Thu, etc.); topics rotate through `canon.topics` offset by what the brand has already covered on that channel.
- Quota: `Brand.weekly_quota[channel]` (default 5) caps open drafts + approved per channel per week.

## 5. Running it locally

```bash
# from the repo root, existing venv
pytest tests/test_marketing_voice_gate.py tests/test_marketing_store.py tests/test_marketing_tools.py tests/test_marketing_api.py
python run_server.py          # MCP at /mcp, REST at /api/marketing/*, admin at /
```

No LLM key → template mode; with `OPENROUTER_API_KEY` set → real drafts. Example intake payload: `seed_data/brand_intake_example.json` (placeholders; edit before use, `locked_claims` is empty on purpose).

In Claude Desktop (server already configured): *"Create a brand called The Climb with Abid from this intake …"* → *"Generate 3 LinkedIn drafts for the week of 2026-11-17"* → *"Approve the second one for Wednesday 9am, reject the first: too generic"* → *"What shipped this week?"*

## 6. What the first paying customer needs (not yet built)

Ordered by what blocks a sale, with the roadmap week.

1. **Hosted instance with login** (wk 6): Postgres, Traefik on the VPS, workspace-scoped auth on marketing tools, per-brand export, nightly dump + restore drill.
2. **OAuth 2.1 on `/mcp`** (wk 7): required by the Claude and ChatGPT connector directories; without it the only path is "paste a URL in developer mode", which the research shows is a hard stop for owners.
3. **Thin UI** (wk 5): Queue, Canon, Week/Log pages in the existing admin. The approval decision must be one click with a reason box.
4. **Billing** (wk 7): Stripe checkout + webhooks + portal + entitlement check, generalised from Belay (`web/src/stripe/webhooks.ts`, `lib/billing.ts`); per-brand tiers from `STRATEGY_V3` §9.
5. **One real publishing path** (wk 3 recipe, wk 10 worker): Buffer MCP for social; listmonk/Resend for email.
6. **Weekly digest** (wk 3): one message per brand per week with the open queue; buttons or links back to the UI.
7. **Data handling**: privacy page, deletion endpoint, DPA on request; agency clients' content is the agency's data.
8. **Support**: a support address, a status page (the VPS Kuma), and a 1-page "how we use your canon with the model" note (OpenRouter, no training).
9. **Website**: `/pricing` and homepage copy that match reality (draft PR on `msgstack-website`).

## 7. Reuse inventory (read-only pass over Syd, voice-lint, Belay, listmonk; 2026-11-16)

Legend: **as-is** = productizable with a rename/import; **generalize** = pattern is right, code is coupled to Abid/LinkedIn/Telegram/n8n; **no** = Abid-specific content. Effort: S = < 1 day, M = 2–5 days, L = > 1 week.

| Component | Where it lives | Verdict | Effort | Notes |
|---|---|---|---|---|
| Deterministic voice lint rules | `C:\Users\Abid\voice-lint\lint_template.js` (489 lines) | **as-is → done** | S (done) | Ported to `src/marketing/voice_gate.py`; layoff/prescribe rules left to `off_limits` |
| Lint rewrite prompt | same file, `rewritePrompt` | **as-is → done** | S (done) | Brand-neutralised in `voice_gate.rewrite_prompt` |
| `sync_lint.py` single-source-of-truth + version stamp | `voice-lint/sync_lint.py`, `voice_lint_gen.py` | generalize | S | Pattern reused as `GATE_VERSION` on every gate result |
| Stage → hard checks → judge → decide pipeline | `syd-memory/content_desk.py` (1,627 lines: `stage`, `hard_checks`, `judge`, `_autopilot_decide`, `decide`, `agreement`) | generalize (~60% generic) | M | Prompts, `personal`/`climb` accounts, n8n resume URLs and Telegram cards are Abid-specific; the stage/decide/labels/lessons core is the Phase 3 judge |
| Score-band enforcement (post ≥8 / hold 5–7 / drop <5) and one-rewrite rule | `content_desk._parse_verdict`, `_autopilot_decide` | as-is (rule) | S | The slice already applies "one rewrite, keep the better" |
| Agreement metric (owner vs judge, ≥15 at ≥90%) | `content_desk.agreement()` | as-is (rule) | S | Gate for autonomy tier 2 |
| Plan Gate / quota with proration and carry-over | `syd-memory/content_plan.py` (115 lines) | **as-is** | S | Slice has the weekly cap; monthly random plan + carry-over is a direct port |
| Weekly audit (keep/edit/delete bands, week-level critique, dry mode) | `syd-memory/content_audit.py` (444) | generalize | M | Bands and run loop generic; LinkedIn URNs and the n8n action workflow are not |
| Digest queue (compose grouped, one morning message) | `syd-memory/digest.py` (302) | **as-is** | S | Telegram sink → Resend/Telegram per brand |
| Autonomy tiers, deny rules, kill switch, circuit breaker | `syd-memory/autonomy.py` (532) | **as-is** | M | `KNOWN_KINDS` list is Syd's; everything else is the agent-layer policy engine |
| Pulse voice lint (`RULES`, `lint()`, `rewrite_instruction`) | `syd-memory/pulse_voice.py` (628) | as-is (rules) | S | Overlaps the ported gate; merge the few extra shapes (setup_pivot, verdict_stub, hype, emoji_pile) |
| Judge rubric, `FEWSHOT`, `RUBRIC`, lessons text | `content_desk.py`, `content_audit.py`, `pulse_voice.py` | **no** | — | Abid's voice; each brand gets its own from labels |
| Golden harness (catch/keep rates, leave-one-out) | `syd-memory/tests/golden_content.py` (181) | as-is (harness) | S | Fixture data is Abid's |
| Real-material brief with privacy filter | `syd-memory/content_material.py` (197) | generalize (pattern) | M | Sources are Syd's tables; the "brief is the only source of facts" rule is already in the slice's `brief` param |
| Model router (pools, fallbacks, cost log, Langfuse) | `syd-memory/model_router.py` (1,058) | as-is | M | MsgStack has `llm_client()`; adopt pools when the judge lands |
| Subscriber mirror + consent-safe listmonk sync | `syd-memory/stores.subscriber_sync_plan`, `dashboard.py` `/api/newsletter/*` | as-is (logic) | S | listmonk list 3 and Resend key are env; semantics (`finished` ≠ delivered, never flip an unsub) carry over |
| Send guard, unsub sync, welcome flow | n8n workflows `PTba2nGlpknjzCd2`, `i2lvr8MP91x7jo1f`, `PB6GysAs06b7dg7B` | generalize | M | Live in n8n, not code; a hosted product needs them in a worker |
| Conversational intake engine (spec + typed draft + missing-fields + merge) | `belay/worker/belay_worker/agents/prep/engine.py` (217), `llm.py` `complete_json` (320) | **as-is (pattern)** | M | The multi-turn version of `brand_intake`; `agents/intake.py` itself is Climb-specific |
| Stripe checkout + webhooks + tier mapping | `belay/web/src/stripe/webhooks.ts` (177), `lib/billing.ts`, `actions.ts` `startCheckout` | generalize | M | Never enabled; no portal, no entitlement check, no tests; env-var prices → price→tier table with workspace id |
| Resend + Telegram delivery, inbound email (Svix) | `belay/worker/belay_worker/channels.py` (240), `inbound_email.py` (303) | as-is / generalize | S–M | Inbound parsing generic; outbound has one global sender |
| Deploy to VPS (`ship.sh`, Traefik, `:prev` rollback, nightly pg_dump) | `belay/deploy/ship.sh`, `deploy/vps/docker-compose.yml` | **as-is** | S | Change host, dir, image names |
| Replay cassette + gate in CI | `belay/worker/belay_worker/replay/` (~230 generic lines) | as-is (pattern) | M | Personas/rubric per product |
| Single-thread web app shell (Thread, Composer, Chips, Sheet) | `belay/web/src/components/` | generalize | L | Only if the owner UI becomes conversational; not in 90 days |
| LinkedIn posting via n8n + report-back | n8n generators + `scripts/content_autopilot_patch.py` | no (replace with Buffer MCP) | — | The token lives in n8n; Buffer removes that dependency |

**Thesis check.** Everything the first three brands need already exists somewhere in Abid's estate: gate (ported), quota (port S), digest (port S), autonomy ladder (port M), newsletter send (listmonk, live), social send (Buffer MCP, external), billing (Belay, generalize M), hosting (Belay pattern, S). The new work is the hosted multi-tenant surface and OAuth, not the marketing logic.
