# Task: v0.9 Governance Wave 2 — Completion & Fixes

**Project:** MsgStack MCP Server
**Location:** `C:\Users\Abid\msgstack-mcp\`
**Milestone:** v0.9 — finish the Content Tiering / DRI / Query Audit Log work

---

## Context

The previous run implemented the schema and store layer for Content Tiering, DRI Ownership, and the Query Audit Log (all currently **uncommitted** in the working tree — nothing has been committed except the docs commit `0c6fb98`). An independent review found the work solid at the schema/store level but incomplete at the enforcement/wiring level, plus **one production-breaking regression and one test failure that was misreported as pre-existing**.

Your job: fix the critical issues, finish the incomplete parts, sync the docs, and commit everything in clean per-part commits.

**Read first:**
1. This file, fully
2. `PRODUCT_SPEC.md` §4.9 (Content Tiering) and §4.12 (Query Audit Log) — the acceptance spec
3. `src/pipeline/generator.py` `_build_context()` (~line 405)
4. `src/store.py` — `log_query` (~line 2911), `update_entry_status` promotion gate (~line 2803), review-trail methods (~line 1450)
5. `src/grounding/tools.py` — the search tool implementations that need audit wiring

**Conventions (unchanged):**
- `pytest` from repo root must end fully green. Run the **full suite** and report the exact pass/fail counts. Do not attribute a failure to a pre-existing cause without proving it (e.g. `git stash && pytest <that test>` to show it failed before your changes too).
- Additive migrations only — the production SQLite DB at mcp.abidc.dev upgrades in place.
- After code changes: `docker compose build && docker compose up -d` to smoke-test at `http://localhost:8001`.
- Warm-beige/terracotta UI theme; match existing card/badge patterns in `dashboard.html`.

---

## Part A — Critical fixes (do these first, commit as `fix:` commits)

### A1. Generator regression: untier'd entries are silently dropped 🚨
`src/pipeline/generator.py` `_build_context()` (~line 414) currently filters out every entry whose `content_tier` is `None`:

```python
messages = [m for m in messages if getattr(m, "content_tier", None) is not None]
```

**Every legacy entry in the production DB has NULL tier**, so artifact generation against the live database grounds on nothing. Remove the filter. Tier affects **ordering and annotation only** in generation; unset tier blocks *promotion* (already handled in `update_entry_status`), never generation. Untier'd entries render with no tier label, sorted after tiered ones.

**Regression test (required):** a domain whose entries all have `content_tier=NULL` generates an artifact whose grounding context contains those entries.

### A2. Query audit log is dead code 🚨
`store.log_query()` exists but has **zero call sites** — nothing ever writes to the table. Wire it in:

- One shared helper (in `src/grounding/tools.py` or a small module both can import) that builds a `QueryAuditLog` from a search call and invokes `store.log_query()`.
- Call it from: the `search_canon` / `search_messaging` MCP paths, `get_grounding_context`, and the web search endpoint in `web_app.py`.
- Populate: `caller` (workspace/API-key name where available, else `"mcp-session"` / `"web"`), `surface` (`mcp`|`web`), `tool_or_endpoint`, `query_text`, `domain_ids`, `entry_ids_returned`, `top_confidence`, `result_count`.
- **Non-blocking:** wrap in try/except — a logging failure must never fail or slow the query (log the exception, continue).
- Tests: one search writes exactly one row with correct entry IDs; a forced logging exception doesn't break the search.

### A3. Failing test, misreported last run
`tests/test_approval_gating.py::TestGetEntryHistory::test_get_entry_history_returns_trail` fails: expects 2 trail events, gets 3 (tier assignment now logs an event — which is correct behavior). Fix the test to assert on **event actions/content** rather than a brittle raw count, so future trail additions don't break it. Confirm the extra event is the tier assignment and that its trail entry is well-formed.

---

## Part B — Finish Tier 1 enforcement (spec §4.9 — currently label-only)

The grounding block only tags entries `[T1 locked]`. That's a label, not a contract. Complete it:

- **B1. Verbatim directives:** In `_build_context()`, Tier 1 entries get an explicit directive, e.g. `[TIER 1 — LOCKED: reproduce this text VERBATIM wherever used. Do not paraphrase, summarize, or alter.]`; Tier 2: `[TIER 2 — preserve substance and positioning; phrasing may adapt.]`; Tier 3 and untier'd: no directive. Also add one block-level instruction in the grounding preamble explaining the tier contract to the model.
- **B2. Post-generation verbatim validation:** after the LLM returns, for each Tier 1 entry that appears to have been used (fuzzy/substring match against the output), verify it appears verbatim. On violation, append a structured warning to the artifact result (`tier_violations: [...]`) — surface, don't hard-fail.
- **B3. Alignment integration:** in `src/pipeline/alignment.py`, include tier in the reference context lines (`- [proof_point | TIER 1] ...`) and instruct both auditor prompts that a paraphrase of a Tier 1 claim classifies as a **hard conflict**.
- Tests: T1 directive present in built context; verbatim violation produces a warning; alignment context contains tier labels.

## Part C — Finish DRI (currently field-only)

- **C1. Review-trail events:** DRI set/change via the PATCH endpoints appends a `dri_transfer` event to the review trail (old value, new value, who). Applies to both domain and entry DRI.
- **C2. Accountability view:** admin UI panel (Dashboard section or a Frameworks tab) grouping domains by DRI — **unowned items first** (no DRI on entry or its domain), each domain showing its staleness state (`is_stale()`). REST endpoint to back it (e.g. `GET /api/dri/summary`).
- Tests: transfer logs a trail event; summary endpoint lists unowned items.

## Part D — MCP exposure

- **D1.** Verify `tier` and `dri` (effective DRI) appear in the entry payloads returned by `search_canon` and `get_canon_domain` MCP tools (`src/grounding/tools.py` — search.py already carries `content_tier`, confirm it survives to the tool response; add `dri`).
- **D2.** Update the `system_instructions` MCP prompt in `src/server.py` to document the tier contract (Tier 1 verbatim / Tier 2 substance / Tier 3 spirit) so AI clients honor it.

## Part E — Query log polish

- **E1.** `get_query_log` + `GET /api/query-log`: add `caller`, `domain_id`, `since` filters (in addition to existing `source`/`limit`).
- **E2.** Startup retention prune: on server start, delete rows older than `QUERY_LOG_RETENTION_DAYS` (default 90, configurable in `src/config.py`). Keep the manual cleanup endpoint.
- **E3.** Admin UI: confirm the audit table view renders; add client-side CSV export if missing.

## Part F — Docs & commits (last)

- **F1. Doc-sync pass** (skipped last run): verify each is implemented in the cited file, then flip `[ ]` → `[x]` in `ROADMAP.md`:
  - v0.9 Alignment Scoring items — `src/pipeline/alignment.py`, `score_content_alignment`/`score_canon_alignment` tools, `/score_alignment` endpoint
  - v0.9 entry status field / approval-gated grounding / element-level RBAC (models + store CRUD) / locked canon / binding-based drift flagging (`store.py` ~1237 `propagation_drift`)
  - v0.9 Temporary Message Layer — `TemporaryCanonOverlayModel`
  - v1.0 Sub-Canons + inheritance types; Bindings Layer
  - v1.1 PPTX/XLSX ingestion + Ingestion Conflict Detection — `extract.py`, `conflict.py`
  - v1.3 Specialized Agents + Canon Navigator — `agents.py`; Controlled Vocabulary — `vocabulary.py`
  - Partial implementations: leave unchecked with a short `(partial: ...)` note.
- **F2.** Flip the v0.9 roadmap checkboxes for Content Tiering, DRI, and Query Audit Log items you've now completed (leave unchecked anything still not done, e.g. tier-aware graph-only retrieval routing if you didn't implement it).
- **F3. Commits** — the working tree currently holds ALL of the previous run's work uncommitted. Commit in this order:
  1. `fix(generation): include untier'd entries in grounding context` (A1)
  2. `fix(tests): make entry-history trail assertions robust to tier events` (A3)
  3. `feat(tiering): schema, promotion gate, tier-aware grounding + verbatim enforcement` (previous tiering work + Part B)
  4. `feat(dri): ownership fields, transfer trail events, accountability view` (previous DRI work + Part C)
  5. `feat(audit): query audit log wired into grounding paths, filters, retention` (previous audit work + A2 + Part E)
  6. `feat(mcp): expose tier and dri in payloads, document tier contract` (Part D)
  7. `docs: sync roadmap checkboxes with implemented state` (F1 + F2)

---

## Acceptance checklist

- [ ] Full `pytest` run is green — report exact counts; no failure excused without proof it predates your changes
- [ ] Fresh DB boots clean AND a copy of the existing `data/msgstack.db` upgrades in place
- [ ] **Artifact generation works against a DB where entries have NULL tier** (the A1 regression test)
- [ ] A `search_canon` MCP call produces a query-log row
- [ ] `docker compose build && docker compose up -d` → dashboard loads; tier selector, DRI panel, audit table all render
- [ ] Working tree clean at the end — everything committed per F3
