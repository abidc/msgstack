# MsgStack v2 — Repositioning Plan

**Status:** Approved, in execution on branch `v2-spec-assertion`
**Date:** 2026-08-07
**Supersedes:** the "organizational canon" framing throughout `PRODUCT_SPEC.md`, `README.md`, and www.msgstack.ai

---

## 0. The decisions

| Decision | Choice |
|---|---|
| Vocabulary | **Spec / Assertion** — `CanonDomain`→`Spec`, `CanonEntry`→`Assertion`, "the canon"→"the graph" |
| Audience | Product marketing → **product/engineering teams and agent builders** |
| What gets cut | **The enterprise governance apparatus**, not the retrieval mechanisms |
| Product shape | Governance platform → **self-hosted agent memory layer** |
| Sequencing | Rename + graph first, website last. No claim ships before the code backs it |

---

## 1. Why this change

The "organizational canon layer" premise has three problems:

1. **"Canon" is insider vocabulary.** It asks the reader to adopt a metaphor before they understand the product. Engineers reading "canon domain" do not think "system of record."
2. **The messaging leads with taxonomy, not mechanism.** Canon domains, grounding types, and content tiers are *organizing concepts*. The actual differentiator — a typed graph with provenance and change propagation — is buried in section 002 of the homepage.
3. **It duplicates the day job.** Nucleus (ServiceNow) is the same concept at enterprise scale. Building a second one in the evenings is wasted effort and creates IP ambiguity.

### The overlap is governance, not marketing

The instinct is that the day-job overlap is "both are about marketing content," and therefore the fix is to swap the audience from PMM to engineering. That is wrong, and it was the error in the first draft of this plan.

Nucleus overlaps on **product shape**: department SMEs owning domains, approval lifecycles, multi-level RBAC, suggestion routing, DRI accountability, content SLAs with breach notifications, health dashboards, CI/CD promotion gates. Swapping the audience while keeping that skeleton produces Nucleus-for-engineers — identical overlap, different nouns.

**Evidence this is the right cut** (verified 2026-08-07, both DBs):

| Table | Rows |
|---|---|
| `users` | 0 |
| `element_permissions` | 0 |
| `artifact_entry_bindings` | 0 |
| `temporary_canon_overlays` | 0 |
| `query_audit_log` | 0 |
| `snapshots` | 0 |
| `review_logs` | 1 |

The entire governance apparatus holds **one row**. It was built because Nucleus made it feel necessary, and never used. It is simultaneously the largest overlap surface and the least-used code in the repo.

## 2. The new premise

> Teams ship faster than their documentation. The facts an agent needs — current API constraints, SLA commitments, deprecation timelines, config defaults, security posture — are scattered across Confluence, Jira, Slack, and stale READMEs. RAG over that pile returns confident, unversioned, unattributable answers.
>
> MsgStack is a self-hosted memory layer for agents. Facts are typed nodes with typed relationships, versions, and provenance. Agents query it over MCP. Exact facts return by graph traversal — verbatim, with a citation. Open-ended questions fall back to vector search over the same corpus. When a fact changes, everything downstream that depends on it flags automatically.

Not a governance platform for organizations. A developer tool: git-native, self-hosted, MCP-first, one `docker compose up`.

### The usefulness test

**Would you point it at your own infrastructure?** That question resolves nearly every scope call in this plan:

- Versioned, provenanced facts served to agents over MCP — **yes, day one.** The homelab's facts currently live in a 400-line `CLAUDE.md` that every agent re-reads from scratch each session.
- DRI accountability views and 4-level RBAC — **no.** Team of one.

Retrieval passes. Governance fails. Cut accordingly.

### Naming collision to manage

"Spec" collides with OpenAPI/AsyncAPI specs, which are an ingestion source. Convention: a MsgStack **Spec** is the governed container; ingested files are always qualified as **source documents** ("ingest your OpenAPI document into the `payments-api` spec"). The DB already calls these `source_files`, so the code side is consistent.

---

## 3. Vocabulary map

### Concepts

| Now | Becomes |
|---|---|
| canon / the canon | the graph |
| Canon Domain | **Spec** |
| Canon Entry | **Assertion** |
| Persona | **Audience** |
| Objection `{statement, response}` | **QAPair** |
| Grounding Type | Schema |
| Sub-canon | Child spec |
| Content Tier, Provenance, Artifact, Binding | *unchanged — already neutral* |
| Canon Owner, Canon Health | **removed** — see §5 |

### Python types (`src/models.py`)

| Now | Becomes |
|---|---|
| `CanonDomain` | `Spec` |
| `CanonEntry` | `Assertion` |
| `DomainStatus` | `SpecStatus` |
| `EntryStatus` | `AssertionStatus` |
| `SectionType` | `AssertionType` *(values fully replaced — §6)* |
| `GroundingType` | `SchemaType` |
| `Persona` | `Audience` |
| `Objection` | `QAPair` |
| `GroundingChunk`, `GroundingContext`, `GroundingResult`, `GroundingResponse` | *unchanged* |
| `PainPoint`, `BuyingTrigger` | **deleted** |
| `UserRole`, `ElementPermission` | **deleted** — §5 |

### Tables (`src/store.py`)

| Now | Becomes |
|---|---|
| `canon_domains` | `specs` |
| `canon_entries` | `assertions` |
| `canon_entry_channel_association` | `assertion_channel_association` |
| `personas` | `audiences` |
| `objections` | `qa_pairs` |
| `canon_domain_id` (FK on ~8 tables) | `spec_id` |
| `canon_entry_id` | `assertion_id` |
| `canon_domain_name` / `canon_domain_summary` | `spec_name` / `spec_summary` |
| `pain_points`, `buying_triggers` | **dropped** (194 rows) |
| `users`, `element_permissions`, `artifact_entry_bindings`, `temporary_canon_overlays`, `snapshots` | **dropped** (0 rows) |

### MCP tools (`src/server.py`)

| Now | Becomes |
|---|---|
| `search_canon` | `search_assertions` |
| `list_canon_domains` | `list_specs` |
| `get_canon_domain` | `get_spec` |
| `set_active_domain` | `set_active_spec` |
| `compare_canon_domains` | `compare_specs` |
| `check_canon_completeness` | `check_spec_completeness` |
| `get_entry_history` | `get_assertion_history` |
| `get_framework_spec` | `get_schema` *(current name becomes actively confusing)* |
| `score_canon_alignment` | `score_alignment` *(alias already exists)* |
| `get_graph_connections` | *unchanged — earns its name in Phase 2* |
| `search_messaging`, `set_active_house`, `get_message_house`, `list_message_houses`, `compare_houses`, `get_message_history`, `check_framework_completeness` | **removed** — §7 |
| `get_query_audit_log`, `get_usage_heatmap`, `get_coverage_report` | **removed** — §5 |

---

## 4. Phase 2 — Make the graph real

The load-bearing phase. Today `src/grounding/graph.py` builds a per-spec *containment tree* — every edge lives inside one spec. `_graph_search()` (`src/grounding/search.py:386`) takes a spec id and applies metadata filters; it does not traverse. `hybrid` mode is "vector first, graph for related context" (`search.py:129`), not a fusion. Cross-spec `INFORMS`/`DEPENDS_ON` exist only in prose.

| # | Work | Notes |
|---|---|---|
| 2a | **First-class entities.** Nodes are `chunk::{id}`, scoped to one spec. Add an `entities` table with cross-spec resolution. | Reuse `secondbrain`'s approach: exact alias match, then >0.90 cosine merge. Note its known gap — the 0.75–0.90 "ask an LLM" band is unimplemented there and defaults to creating a new entity |
| 2b | **Typed cross-spec edges.** New `edges` table: `DEPENDS_ON`, `INFORMS`, `SUPERSEDES`, `CONTRADICTS`, `OWNS`, `IMPLEMENTS` — with confidence, provenance, creator. | Replaces the containment-only edge set |
| 2c | **Real traversal.** Rewrite `_graph_search` as k-hop expansion from seed nodes, with edge-type filters and path scoring. | Current filter-by-spec behaviour becomes one degenerate case |
| 2d | **Real hybrid fusion.** Vector recall → graph expansion → reciprocal-rank fusion → rerank. | This is the specific claim the new site makes. Build before claiming |
| 2e | **Change propagation.** On assertion update, walk inbound `DEPENDS_ON`/`INFORMS`, mark downstream `Outdated`, notify. | The one piece of governance worth keeping — it is a graph mechanism, not a workflow |
| 2f | **Scaling honesty.** Graph is rebuilt in-memory from DB on start (`PRODUCT_SPEC` §8). | Fine at current scale. Document as a known limit; do not claim otherwise |

### Phase 2 — as built (2026-08-07)

Delivered: `entities` / `entity_mentions` / `edges` tables; `RelType` vocabulary
with `PROPAGATING_RELS`; `GraphEngine.expand()` k-hop traversal; RRF fusion in
`_fuse_with_graph`; transitive `propagate_change()`; MCP tools `traverse_graph`,
`get_impact`, `link_assertions`. 24 tests in `tests/test_graph.py`.

Verified on a copy of the live database: two assertions in different specs are
unreachable from each other until a shared entity links them, then reachable in
exactly 2 hops via `->MENTIONS <-MENTIONS`; editing one marks the other outdated
across the spec boundary.

**Two design decisions worth keeping:**

*Hub guard.* The first working traversal connected everything to everything.
Nearly every assertion carries channel `"all"`, so walking `APPLIES_TO` put every
assertion two hops from every other one through the shared Channel node — the
graph degenerated into a complete graph and traversal was worthless while
appearing to work. Fixed two ways: `APPLIES_TO`/`CONTAINS`/`HAS_SECTION` are
non-traversable (they are containment scaffolding, not relationships), and any
node above `_HUB_DEGREE` may be *reached* but never expanded *through*. The
degree guard is the general form and protects against future hub-like nodes.
Regression tests: `test_shared_channel_does_not_connect_unrelated_assertions`,
`test_hub_node_is_not_traversed_through`.

*No fuzzy entity merging.* `resolve_entity` matches on normalized name or
registered alias only. The >0.90-cosine auto-merge from the original design is
deliberately not implemented: a false merge silently fuses two unrelated
services and is far harder to notice than a duplicate. Ambiguous cases stay
separate and are merged explicitly via `merge_entities()`.

## 5. Phase 3b — Cut the governance apparatus

This is the day-job separation. All of it is unused (§1).

**Removed:**
- `ElementPermission` RBAC and the 4 permission levels (Owner / Collaborator / Suggester / Viewer)
- Suggestion routing and the change-review/approval workflow
- Content SLA: review cadence, trigger events, breach notifications, SLA dashboard
- Canon Health score and dashboard
- Content CI/CD promotion pipeline and gated Draft→Approved promotion
- Golden Query Dataset and retrieval benchmarking
- Temporary priority overlay layer
- Query audit log, usage heatmap, coverage report
- "Gold standard" content designation
- `users` table and identity-scoped retrieval (SSO)
- DRI as an accountability *system* — the `dri` field survives as a plain provenance string, but the ownership-transfer flow and unowned-items view go

**Kept — what a dev tool actually needs:**
- **Provenance** — every result traces to its source assertion and document
- **Versioning** — assertion history and change trail
- **`locked` flag** — the one lifecycle bit that matters, driving Tier 1 verbatim retrieval
- **Content tiers** — the best idea in the product; a generation contract, not a workflow
- **Change propagation** (2e) — a graph mechanism

The five-state lifecycle (`Draft`/`In Review`/`Approved`/`Outdated`/`Locked`) collapses to three: `draft`, `active`, `outdated`, plus an orthogonal `locked` boolean. `In Review` has no meaning without an approval workflow.

## 6. Phase 3 — Re-aim the schema at engineering

### Deleted
- **Tables:** `pain_points`, `buying_triggers` (194 rows)
- **Models:** `PainPoint`, `BuyingTrigger`
- **`SectionType` values:** `headline`, `subhead`, `benefit`, `proof_point`, `social_proof`, `know_your_market`, `brand_voice`, `competitor_strength`, `competitor_weakness`, `competitive_response`, `narrative_pillar`, `founding_story`, `company_value`
- **`GroundingType` values:** `message_house`, `brand_guide`, `competitive_brief`, `corp_narrative`, `persona_library`
- **Skills** (`data/skills/`): `battlecard`, `sales_deck`, `press_release`, `linkedin_post`, `objection_handler`, `partner_brief`, `talk_track`, `email_template`, `event_brief`, `event_presentation`
- **Pipeline:** the dedicated persona-extraction LLM call in `src/pipeline/structure.py` is rewritten for audiences, not deleted

### Kept, renamed — general mechanisms that were wearing PMM clothes
- **`Persona` → `Audience`.** Audience-conditioned retrieval is core, not PMM: the same assertion renders differently for a new hire, an on-call SRE, and an integrating partner.
- **`Objection` → `QAPair`.** The `{statement, response}` shape is FAQ, known-issue/workaround, and ADR rejected-alternatives — one of the most useful retrieval shapes there is.
- **`channel_variants` / `Channel`.** Same assertion for Slack vs. changelog vs. API reference.
- **Neutral skills:** `faq_document`, `executive_summary`, `one_pager`, `blog_post` are document types, not PMM artifacts.

### Added
**`AssertionType`** (replaces `SectionType`): `constraint`, `sla`, `deprecation`, `config_default`, `dependency`, `capability`, `limitation`, `security_posture`, `interface_contract`, `version_policy`, `runbook_step`, `decision`

**`SchemaType`** (replaces `GroundingType`, `engineering_spec` default): `engineering_spec`, `service_catalog`, `policy_shield`, `incident_record`

**Skills:** `release_notes`, `api_changelog`, `deprecation_notice`, `adr`, `incident_comms`, `runbook`, `rfc_summary`, `onboarding_doc`, `integration_guide`

**Ingestion:** OpenAPI/AsyncAPI documents, GitHub READMEs and ADRs, Jira, postmortems

### Data migration

Backups taken 2026-08-07 → `data/archive/msgstack.db.bak-pre-v2`, `data/archive/msgstack-root.db.bak-pre-v2`.

| DB | specs | assertions | audiences | qa_pairs | *dropped* pain_points | *dropped* buying_triggers |
|---|---|---|---|---|---|---|
| `data/msgstack.db` *(live)* | 11 | 34 | 34 | 84 | 84 | 84 |
| `msgstack.db` *(root, stale)* | 21 | 63 | 63 | 26 | 26 | 26 |

**194 rows dropped.** All 97 assertions carry `section_type` values that no longer exist and need a mapping pass — anything unmappable gets `capability` plus a `needs_review` flag, never silent deletion.

## 7. Phase 4 — Rename sweep

Reuse the playbook from the `message_house` → `canon_domain` rename, still in the code:
- Guarded `ALTER TABLE ... RENAME` migrations, pattern at `src/store.py:649-724`
- Pydantic `AliasChoices` on renamed fields, pattern throughout `src/models.py`
- Extend `tests/test_alias_compat.py`

**Order:** `models.py` → `store.py` + migrations → `grounding/` → `pipeline/` → `web_app.py` → `server.py` → `src/web/*.html` → `tests/`

**Scale:** 702 occurrences across 13 source files, 3 Jinja templates, 7 test files, 8 docs.

### Alias debt

The codebase carries **generation-1 aliases** (`message_house`, `house_id`, `key_message`) from the last rename — `AliasChoices` on ~10 model fields, 7 deprecated MCP tools, and internal parameter names throughout `grounding/tools.py`, which still uses `house_id` natively.

**Drop generation-1 entirely in this pass.** Two generations of aliases is worse debt than one clean break. Only `canon_*` → `spec_*`/`assertion_*` aliases carry forward, for one version.

## 8. Phase 5 — Website

- **Nav:** "The Canon" → "The Graph". `/canon` → `/graph` (301). `/message-house` → `/schemas`. `/governance` retired or folded into `/graph` as change propagation.
- **Homepage:** hero rewrite on the §2 premise. Section 002 becomes the graph/traversal explainer (`FakeGraph.tsx` is the starting point). Section 003 grounding-types folds into schemas. Section 004 governance reframes from "approval workflow" to "change propagation."
- **Components:** `CanonLayerStack.tsx` → `GraphExplorer`; `TypewriterCanon.tsx` retired; `HybridGroundingSection.tsx` rewritten around real fusion; `GroundingMatrix.tsx` and `AnatomyVisualizer.tsx` reworked for audiences or deleted.
- **Demos:** the terminal at `src/app/page.tsx:202-223` shows *"98% of zero-day threats stopped proactively"* and a sales email. Needs an API constraint and a release note. `GroundingChecker.tsx` reframes from an SDR email to a release-note claim.
- **Honest-claims audit.** The stat row (`page.tsx:230-248`) asserts "100% deterministic retrieval," "0 drift shipped," "<1ms." Every number maps to something real and measurable, or it comes out.

## 9. Phase 6 — Docs

`PRODUCT_SPEC.md` §1, §2, §2.8 are full rewrites — §2.8 alone defines 20 canon-based terms, and §3.5's nine "strategic gaps" are mostly the governance apparatus being cut. Then `README.md`, `ROADMAP.md`, `AGENT_GUIDE.md`, `docs/ARCHITECTURE.md`, `docs/BRAND_GUIDELINES.md`.

---

## 10. Execution order

```
Phase 0   Vocabulary + scope decisions           ✓ done
Phase 1   Narrative                              ✓ this file
Phase 3b  Cut the governance apparatus           ✓ done — reordered ahead of
                                                  Phase 4 so deleted code was
                                                  never renamed first
Phase 4   Rename sweep + alias-debt cleanup      ✓ done
Phase 2   Make the graph real                    ✓ done — see "as built" above
                                                  ← next: entity extraction
Phase 3   Schema rewrite + eng re-aim            destructive — backups taken
Phase 5   Website                                claims now backed by code
Phase 6   Docs
```

Rename precedes the graph work so all new code is written in the final vocabulary. Phase 3b runs before Phase 2 so the graph rewrite doesn't carry governance semantics through it.

## 11. Risks

| Risk | Mitigation |
|---|---|
| 194 rows dropped in Phase 3 | Backups taken; JSON export before the migration runs |
| 97 assertions orphaned by `SectionType` removal | Mapping pass; unmappable → `capability` + `needs_review`, never silent deletion |
| Second rename in the product's life | Single clean break — generation-1 aliases dropped in the same pass (§7) |
| Site over-claims a graph that doesn't traverse | Phase 2 precedes Phase 5 by design |
| "Spec" collides with OpenAPI specs | Ingested files always qualified as "source documents" (§2) |
| Cutting governance removes a real differentiator | It has 1 row across both DBs after a year. It is not a differentiator; it is the day-job overlap |
| Existing stat-row claims unverifiable | Honest-claims audit in Phase 5 (§8) |
