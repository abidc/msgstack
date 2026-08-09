# MsgStack — Product Specification

**Version:** 2.0.0-dev
**Last Updated:** 2026-08-07
**Status:** Active Development — Open Source (Apache 2.0)
**Repository:** https://github.com/abidc/msgstack-mcp
**Website:** https://www.msgstack.ai

> **v2 repositioning is in progress.** `STRATEGY_V2.md` is the current source of
> truth for scope and vocabulary. Sections below that describe governance
> workflows (RBAC, approval routing, content SLAs, health dashboards, CI/CD
> promotion gates, golden query datasets) describe features that were **removed
> in v2** and are retained here only until this document is fully rewritten.

---

## 1. Problem Statement

Teams ship faster than their documentation. The facts an agent needs to answer
correctly — API constraints, SLA commitments, deprecation timelines, config
defaults, security posture — are scattered across Confluence, Jira, Slack and
READMEs that nobody has reviewed in a year.

Retrieval-augmented generation over that pile produces confident, unversioned,
unattributable answers:

- A copilot drafts release notes and invents a rate limit that was lowered last sprint.
- A support agent quotes an SLA from a page nobody owns.
- An integration guide keeps promising a parameter deprecated two versions ago.

The failure is not retrieval quality. **A fact has dependencies; an embedding
does not.** Vector search finds text resembling the question. It cannot know
that the number just quoted is downstream of a gateway policy that changed on
Tuesday, because that relationship is not something cosine similarity can
represent.

---

## 2. Vision

> A self-hosted memory layer for agents. Facts are typed nodes with typed
> relationships, versions and provenance. Agents query it over MCP. Exact facts
> return by graph traversal with a citation; open questions fall back to vector
> search over the same corpus. When a fact changes, everything downstream that
> depends on it is invalidated automatically.

The product is a **developer tool**, not a governance platform: git-native,
self-hosted, MCP-first, one `docker compose up`. Governance is deliberately
limited to what a dev tool needs — provenance, versioning, a locked flag, and
change propagation. There is no RBAC, no approval routing, no SLA breach
notification, and no compliance audit log; see `STRATEGY_V2.md` §5 for why.

The primary users are product and engineering teams, and the people wiring
agents into their own stacks.

---

## 2.8 Core Vocabulary & Concepts

- **Spec:** A governed container for facts about one service, component or policy scope. Ingested OpenAPI documents and READMEs are *source documents* that fill a spec — they are not specs themselves.
- **Assertion:** One atomic, typed fact within a spec. Carries an assertion type, lifecycle status, content tier, owner and priority.
- **Assertion Type:** What kind of fact it is — `constraint`, `sla`, `deprecation`, `config_default`, `dependency`, `capability`, `limitation`, `security_posture`, `interface_contract`, `version_policy`, `runbook_step`, `decision`, `positioning`.
- **Schema Type:** The shape of a spec — `engineering_spec` (default), `service_catalog`, `policy_shield`, `incident_record`.
- **Entity:** A concept assertions refer to (a service, endpoint, component). Entities are **workspace-scoped, not spec-scoped** — that is precisely what allows a traversal to leave one spec and arrive in another.
- **Edge:** A typed, directed relationship between any two nodes: `DEPENDS_ON`, `INFORMS`, `SUPERSEDES`, `CONTRADICTS`, `OWNS`, `IMPLEMENTS`, `MENTIONS`. Carries confidence and provenance.
- **Propagating relationships:** `DEPENDS_ON` and `INFORMS` cascade staleness from destination to source. The rest are navigational and do not invalidate anything.
- **Traversal:** Breadth-first k-hop expansion from seed assertions, walking edges in both directions with per-relationship weight decay, returning the path that reached each result.
- **Fusion:** Reciprocal rank fusion of vector recall with a graph expansion seeded from its top hits. A result found by both routes outranks one found by either alone.
- **Content Tier:** A per-assertion generation contract, orthogonal to lifecycle status: *Tier 1 — Locked* (verbatim, validated post-generation), *Tier 2 — Structured* (substance preserved, phrasing adaptable), *Tier 3 — Grounded* (direction preserved, full phrasing latitude).
- **Audience:** Who an assertion is being rendered for. Audience-conditioned retrieval is a general mechanism — the same constraint reads differently for a new hire, an on-call engineer and an integrating partner.
- **QAPair:** A `{statement, response}` pair. Serves FAQ entries, known-issue/workaround pairs, and the rejected-alternatives section of an ADR.
- **Provenance:** The verifiable trace from any generated output back to the exact assertions and source documents that grounded it.
- **Derived Artifact:** A downstream document (release notes, ADR, runbook, changelog) generated strictly from approved assertions in a spec.
- **Hub guard:** Traversal never continues *through* a node above a degree threshold, and never walks containment edges (`APPLIES_TO`, `CONTAINS`, `HAS_SECTION`). Without this the graph degenerates — nearly every assertion carries channel `"all"`, which would put every assertion two hops from every other one.

---

## 2.5 Open Source Model

MsgStack is **Apache 2.0 licensed** and fully self-hostable. The core product — MCP server, admin UI, knowledge graph, artifact generation — will always be open source.

---

## 3. Target Users & Graph Owners

### Primary: Spec Owners (Department SMEs)
- **Product Managers:** Define product capabilities, specs, release details, and roadmap facts.
- **Product Marketers:** Own and maintain the specs, positioning pillars, and buyer audiences.
- **Legal & Compliance Officers:** Own legal disclaimers, liability warnings, and trademark guidelines.
- **HR & Security Administrators:** Own HR guidelines, employee handbooks, security posture highlights, and SOC 2 answers.
- SMEs control which assertions are `Approved` vs `Draft` and review dependency alerts.

### Secondary: Field Teams & Downstream Consumers
- **Field Marketing & Sales Enablement:** Generate localized, audience-specific battlecards, emails, and pitch decks.
- **Customer Success & Support Agents:** Query the security, HR, or product graph for verified answers.
- **Access Path:** Utilize the Self-Service Field Portal to consume approved graph without editor/admin rights.

### Tertiary: External Agencies & Partners
- Access read-only views of specific specs.
- Generate draft assets that require approval by the internal Spec Owner before distribution.

### Quaternary: AI Agents & Assistants (Claude, ChatGPT, Cursor, Copilot)
- MCP clients querying grounding context directly during developer, writer, or ops sessions.
- Automatically verify alignment of generated outputs before submitting for human review.

---

## 3.5 Strategic Gaps — Value Drivers for Enterprise Governance

The core build solves the technical grounding problem. The features below translate that into an enterprise-wide platform that compliance, brand, and operations teams trust.

### Gap 1 — Alignment Scoring (Continuous Governance)
MsgStack can ground AI generation, but it must also evaluate content that already exists — whether a draft post, an email sequence, or a developer document — and score it against the approved graph.
- **The Value:** Paste draft content or connect a content library (HubSpot, Google Docs) and receive a per-section alignment score.
- **What it flags:** Distinguishes between hard conflicts (factual/positioning contradictions) and softer subjective misalignments (e.g., brand voice deviations).
- **External Export:** Comments, highlights, and alignment scores can be exported back to third-party partners (like a PR agency) for revisions.
- **Feedback Loop:** Generates a weekly "drift report" showing where published or saved content has diverged from updated graph.

### Gap 2 — Governance & Approval workflows
Without gated generation, graph is suggestion, not authority. SMEs need structured workflows to move assertions from draft to live grounding.
- **Status lifecycle:** `Draft` | `In Review` | `Approved` | `Outdated` | `Locked`.
- **RBAC at the Atomic Element Level:** Every element has defined owners and collaborators, with four permission levels: *Owner*, *Collaborator*, *Suggester*, and *Viewer*.
- **Suggestive Change Workflow:** Users without authority to change an element can only make suggestions. Suggestions route automatically to the designated owner for approval.
- **Change Review & Approval:** When an authorized user updates a graph element, downstream owners are notified, receiving conflict review sets to accept, decline, suggest edits, or escalate changes.
- **"Gold Standard" Content Designation:** Ability to flag specific deliverables as the canonical reference version that all other related assets should conform to.
- **Dependency Tracking:** When a Product PM updates a specification in the product graph, all downstream marketing specs and legal guidelines that depend on that specification are flagged as `Outdated`.

### Gap 3 — Self-Service Graph Portal
Stakeholders like sales reps, regional teams, and external writers do not need the complex Admin UI. They need a simple, self-service search and generation dashboard.
- **The Value:** A shareable, login-free portal scoped to specific approved specs.
- **Capabilities:** Choose channel → choose audience → generate grounded copy. Cannot edit the source graph.
- **Agency approval flow:** Generated drafts are held in a pending queue for SME approval.

### Gap 4 — Ingestion & Ingestion Pipeline
- **Rich Ingestion:** Ingest documents, decks, spreadsheets, transcripts, voice memos, and unstructured notes.
- **Agentic Placement:** Specialized ingestion agents analyze raw material and recommend where to structure it in the graph.
- **Ingestion Conflict Detection:** The ingestion pipeline automatically flags where incoming materials contradict existing graph elements.

### Gap 5 — Content Generation & Custom Controls
- **Deliverable Templates:** Supports 50+ templates (CEO keynotes, sales decks, battlecards, press releases, investor updates, product messaging frameworks, etc.) derived from real-world client deliverables.
- **Tonal Sliders:** Brand voice controls with interactive sliders adjusting register (e.g., regulatory IR presentation vs. conversational social post) while staying within brand parameters.
- **Controlled Vocabulary:** Active vocabulary restriction filters that flag or avoid banned terms, competitor-associated words, or target phrases.
- **Annotations & Citations:** Every generated deliverable is annotated with source citations linking directly back to the specific grounded graph elements.
- **Direct Live Pulls & Bindings:** Deliverables link to the graph in real-time, allowing updates to automatically propagate to connected assets.

### Gap 6 — Channel Publishing Integrations & MCP
- **Integrations:** HubSpot (email drafts and social campaigns), LinkedIn (social posts), Salesforce (snippet library for sales reps), Google Docs (collaboration folder).
- **MCP Server Connectivity:** Full MCP server access allowing external tools (like Claude, ChatGPT, Gemini) to pull live grounded graph in real-time. Allows users to stay within their preferred workspace while maintaining live alignment.
- **Slack:** Slash commands (`/msgstack query HR compliance`) return grounded facts directly in chat.

### Gap 7 — Agentic Layer
- **Specialized Agents:** Multiple functional agents specializing in governance, brand voice, and narrative structure.
- **Graph Navigator:** A natural conversation interface acting as the primary user experience wrapper for querying graph status and narrative drift.
- **Human-in-the-Loop Governance:** Core design principle allowing auto-accept modes or manual confirmation for all agent recommendations.

### Gap 8 — Change Propagation
- **Drift Notifications:** Automatic alerts sent to downstream owners of in-flight deliverables when a source graph element changes.
- **Temporary Layer:** Allows leadership to inject a priority message overlay above the graph for a defined timeframe without committing it permanently to database records.

### Gap 9 — User Experience
- **Personalized Dashboards:** Role-scoped dashboard showing recent activity, pending approvals, and notifications based on governance permissions.
- **Graph Health View:** Admin panel rendering a visual overview of where narrative coherence is breaking down across the graph.

### 4.1 Spec Specifications

| Section | Required | Purpose |
|---|---|---|
| Summary | Yes | 2-3 sentence overview of the domain's product or service |
| Target Audience | Yes | Target buyer and user roles |
| Positioning | Yes | Core statement of what the domain targets and why it matters |
| Tagline | Yes | ≤7 word punchy headline |
| Differentiation | Yes | Key differentiators |
| Brand Personality | No | Tone, voice, word choices |
| Assertions | Yes (min 8) | Headlines, benefits, use cases, SLAs, objections |
| Audiences | Yes (min 1) | Buyer/user audiences with triggers and objections |
| Graph Pillars | No | Strategic theme groupings for entries |
| Know Your Market | Optional | Research pre-section (vision, before/after, FOMO, competition) |

**Completeness Scoring:** Each domain is scored 0-100 against the spec. The score drives the "Missing Sections" UI and AI-fill prompts.

**Grounding Types:** The `schema_type` field (aliased as `document_type` for backward compatibility) defines the schema category. Each type defines a department-specific field structure and retrieval contract.

**Grounding Types Registry**

| Type | Status | Department | Schema Focus |
|------|--------|------------|--------------|
| `engineering_spec` | **ACTIVE** | Engineering | Capabilities, interface contracts, constraints, version policy |
| `engineering_spec` | **PLANNED — v1.0** | Engineering | API constraints, system SLAs, versioning policy, deprecation notices |
| `policy_shield` | **PLANNED — v1.0** | Legal & Compliance | Legal disclaimers, privacy rules, compliance assertions, approved responses |
| `brand_guide` | BACKLOG | Brand / Design | Voice, tone, visual identity, approved terminology |
| `competitive_brief` | BACKLOG | Product / GTM | Competitor claims, differentiators, battlecard entries |
| `corp_narrative` | BACKLOG | Communications | Company story, executive messaging, investor-facing claims |
| `persona_library` | BACKLOG | Research / Marketing | Buyer audiences, pain points, buying triggers across segments |

`engineering_spec` is the default and the only fully implemented schema today. All others map to dynamic schema extensions in v1.0+.

### 4.2 Document Ingestion Pipeline

Three-stage pipeline triggered on file upload:

**Stage 1 — Text Extraction** (`extract.py`)
- PDF: `pypdf`, page-by-page with structure preservation
- DOCX: `python-docx`, paragraphs + tables with document-order preservation and merged-cell deduplication
- TXT/MD: utf-8 / latin-1 / cp1252 fallback chain
- Output: raw text string

**Stage 2 — LLM Structuring** (`structure.py`)
- Model: GPT-4o-mini (temperature 0.3, max 4000 tokens)
- Input: up to 24,000 chars of raw text (multi-chunk + merge for larger documents)
- Prompt maps diverse document formats to the canonical schema
- Audience extraction uses a dedicated second LLM call with `response_format=json_object`
- Output: `StructuredDomain` with all fields, `missing_sections` list, and `audiences` with `pain_points`, `buying_triggers`, `objections` as `{statement, response}` pairs

**Stage 3 — Persistence + Indexing**
- SQLite/PostgreSQL: `Spec`, `Assertion[]`, `Audience[]`, `Pillar[]` saved via SQLAlchemy ORM
- **Markdown Proxy File** (`v0.8.2`): raw extracted text saved as `data/sources/{domain_id}.md` — a clean, complete, structure-preserving document that is never LLM-truncated
- Turbovec (local, in-process): each entry + domain fields + KYM block vectorized and upserted (`text-embedding-3-small`, 1536 dims)
- Source Markdown chunks indexed separately under `source_markdown` section type for full-content RAG retrieval including tables and complex formatting
- Knowledge Graph: rebuilt in-memory (NetworkX DiGraph) from DB with full entity-relationship structure

### 4.3 Grounding Architecture

Two complementary retrieval layers:

**Vector Layer (Turbovec — local, in-process)**
- Query pipeline: embed → Turbovec query → metadata filter → keyword overlap rerank
- Use case: exploratory queries, thematic similarity, broad searches
- Results approximate by design — "nearest neighbor" semantics
- No external service required; index stored at `data/msgstack_vectors.tvim`

**Source Markdown Layer** (`v0.8.2`)
- Raw extracted document text (full tables, headings, structured sections) chunked and indexed under `source_markdown` section type
- Retrieved alongside structured chunks during grounding to provide verbatim document context

**Graph Layer (NetworkX DiGraph)**
- Query pipeline: graph traversal via typed edges — no approximation
- Use case: governance queries, verbatim approved content, exact taglines and locked SLAs
- Node types: `Spec`, `Section`, `Pillar`, `Assertion`, `Audience`, `QAPair`, `Channel`, `Entity`
- Edge types: `CONTAINS`, `TARGETS`, `ADDRESSES`, `APPLIES_TO`, `HAS_PAIN_POINT`, `HAS_TRIGGER`, `HAS_OBJECTION`, `RESOLVES`

**Retrieval Mode Routing** (via `retrieval_mode` parameter):
- `vector` — Turbovec semantic search only
- `graph` — Graph traversal for deterministic retrieval
- `hybrid` — Vector first, graph for related context (default)
- `keyword` — SQLite full-text fallback

**Fallback chain:** Vector → Keyword (if Turbovec index missing or empty). Graph traversal works regardless of vector index status.

**Session tracking:** Active spec, used chunks, confidence level, audience context.

### 4.4 Artifact Generation

**Grounding contract:** `generate_artifact` loads ALL approved assertions from the domain (grouped by section type, sorted by priority — no caps), ALL audiences with complete attributes (pain points, buying triggers, objections), and full brand positioning. A structured grounding block is prepended to every prompt with an explicit instruction: "do not introduce capabilities, statistics, or claims not present here."

**Skill Templates** (`generator.py` + `skills.py`)
- 12 pre-built skill templates stored as JSON in `data/skills/`
- Each skill has a `prompt_template` and `sections` definition
- `_build_context()` builds a structured context block grouping assertions by section type with per-group entry counts and priority ordering
- Default skill files always written on server start — template improvements land automatically
- Output: `GeneratedArtifact` with raw LLM content + parsed sections dict + full `grounded_messages` list

**Direct Generation** (`web_app.py`)
- Per-section LLM generation for filling missing spec sections

### 4.5 Visual Artifacts

`one_pager` and `one_pager_visual` skills both route to the Fabric.js canvas at `/canvas?artifact_id={id}`. The canvas app renders a basic zone structure (hero, positioning, entries) from the LLM-generated design spec.

Legacy HTML pages remain at `/artifact/{type}/{domain_id}` for `social_posts`, `battlecard`, and `email_sequence`.

#### Design JSON Schema (v2 — Target)

```json
{
  "schema_version": 2,
  "page": {"width": 816, "height": 1056, "orientation": "portrait", "margin": 40},
  "brand": {"primary": "{{brand.primary}}", "font_heading": "{{brand.font_heading}}"},
  "zones": [
    {
      "id": "header",
      "type": "header",
      "row": 1, "col": 1, "colspan": 12,
      "logo_zone": true,
      "product_name": "HR Service Delivery",
      "background": "{{brand.primary}}"
    },
    {
      "id": "hero",
      "type": "hero",
      "row": 2, "col": 1, "colspan": 12,
      "text_content": "Automate busywork and free time for strategic HR work.",
      "text_style": "heading",
      "subtext": "ServiceNow AI Agents autonomously resolve HR tasks...",
      "background": "{{brand.secondary}}"
    },
    ...
  ]
}
```

#### Content-to-Zone Mapping Rules

| Zone | Source Field | Selection Rule |
|---|---|---|
| `hero.text_content` | `tagline` | Exact tagline value |
| `hero.subtext` | `positioning` | First 2 sentences |
| `pillar_grid.items[].headline` | `differentiation` | Split by bullet; max 6 words each |
| `pillar_grid.items[].body` | `differentiation` | Supporting sentence for each bullet |
| `message_list.items` | `key_messages` (assertions) | Top 6 by priority; group by assertion_type |
| `persona_strip.audiences` | `audiences` | First 3 by completeness score |
| `proof_block.stats` | `key_messages` (assertions) where type=`proof_point` | Top 3; must contain a number |
| `cta_footer.cta` | `positioning` | Last sentence rewritten as imperative |

#### Rendering Paths

**Path A — Fabric.js (graphic artifacts):** Targets `datasheet`, `battlecard`, `social_card`, `event_brief`.

**Path B — reveal.js (presentations):** Targets `sales_deck`, `event_presentation`, `executive_readout`.

**Path C — Penpot (design export):** Targets artifacts requiring pixel-perfect quality.

### 4.6 MCP Server Interface

Exposed via FastMCP (SSE transport):

**Category: Grounding** — `search_assertions`, `set_active_spec`, `get_spec`, `list_specs`, `get_graph_connections`, `compare_specs`, `get_grounding_context`, `reset_conversation`, `list_channels`

**Category: Artifacts** — `generate_artifact`, `build_ui_artifact`, `list_skills`

**Category: Admin** — `check_framework_completeness`, `get_schema`, `get_assertion_history`, `list_mcp_tools`

*Backward compatibility:* Legacy tool names (`list_message_houses`, `search_messaging`, `set_active_house`, `get_message_house`, `compare_houses`, `get_message_history`) are preserved as deprecated aliases.

### 4.7 Admin UI

Jinja2 template system serve SPA at `/`.

### 4.8 Governance Lifecycle (v0.8.3)

Each Assertion has a `status` field that determines whether it appears in grounding results:

| Status | Visible by default? | Description |
|--------|-------------------|-------------|
| `Draft` | No | Initial state — entry being authored, not ready for consumption |
| `In Review` | No | Awaiting SME approval |
| `Approved` | Yes | Active, approved graph — included in all grounding queries |
| `Locked` | Yes | Immutable anchor entry — visible and uneditable |
| `Outdated` | No | Previously approved but superseded — hidden until replaced with new Approved version |

**Gating behavior:**
- All grounding tools (`search_assertions`, `get_spec`, `compare_specs`) default to hiding entries with status `Draft`, `In Review`, or `Outdated`.
- The `include_unapproved=True` parameter overrides the gate, returning all entries regardless of status.
- `get_assertion` (single ID lookup) always returns the entry regardless of status — direct retrieval by ID is unfiltered.
- Internal admin/store methods (snapshots, heatmap, coverage, indexing) always pass `include_unapproved=True` so operational views see the full picture.
- Artifact generation (`generate_artifact`) uses the same filtered pipeline — generated outputs are grounded only in approved and locked entries.

**Entry History:**
The `get_assertion_history(entry_id)` MCP tool exposes the full audit trail for a Assertion:
- Status transitions with timestamps and previous/current values
- Content changes across updates
- Who or what triggered each change (when provenance is recorded)

### 4.9 Content Tiering (Planned — v0.9)

Lifecycle status answers "is this entry ready?" — tier answers "how may an LLM use it?" The two are orthogonal: an `Approved` entry can be any tier.

| Tier | Label | Generation Contract | Retrieval Path |
|------|-------|--------------------|----------------|
| Tier 1 | Locked / Verbatim | Returned and used exactly as written. No paraphrasing, no approximation. | Graph traversal only — deterministic, never nearest-neighbor |
| Tier 2 | Structured / Guided | Substance and positioning preserved; phrasing adaptable to context. | Hybrid (vector + graph) |
| Tier 3 | Grounded / Flexible | Direction and tone consistent with the graph; full phrasing latitude. | Vector |

**Enforcement points:**
- `tier` field on every Assertion; tier tagging required before an entry can transition to `Approved` (validated at promotion).
- `generate_artifact` grounding block carries per-entry tier instructions — Tier 1 entries are injected with an explicit "reproduce verbatim" directive and validated post-generation.
- Tier 1 retrieval always routes through the knowledge graph, bypassing vector approximation entirely.
- Alignment scoring treats a paraphrased Tier 1 entry as a hard conflict.

### 4.10 Content SLA & Freshness Triggers (Planned — v0.9)

Replaces the static 90-day staleness flag with a per-domain operational contract:

- **Review cadence:** Each domain declares its own review interval (e.g., quarterly for positioning, per-release for competitive claims).
- **Trigger events:** An API/webhook registers events — product release, competitive move, market shift — that open an SLA review window on affected domains regardless of cadence.
- **Breach notifications:** When a window closes without review, the domain owner and DRIs are notified and the domain is flagged `needs_review`.
- **SLA dashboard:** Admin view of every domain's SLA state — in-window, due, breached — with last-reviewed dates and open trigger events.

### 4.11 Dual Output — Citation-Marked Review Copy (Planned — v0.9)

Every generated artifact is produced in two renditions:
- **Review copy:** Inline chunk-level citations — source assertion, source document, tier, DRI, last-reviewed date — linked back to the entry in the admin UI. This is what a reviewer validates before publishing.
- **Clean deliverable:** The same content with no citation clutter, ready to ship.

### 4.12 Query Audit Log (Planned — v0.9)

Complements the per-entry review trail with retrieval-side accountability: every grounding query (MCP and web) is logged with the caller identity, query text, content returned (entry IDs), confidence scores, and timestamp. Admin-accessible view with filtering and export. This log also feeds acceptance-signal analytics and identity-scoped retrieval auditing.

---

## 5. Integration Points

### OpenAI API
- Structuring: GPT-4o-mini (low temperature for consistency)
- Generation: GPT-4o-mini (higher temperature for creativity)
- Embeddings: text-embedding-3-small (1536 dims)

### Turbovec (Local Vector Index)
- Quantized local index storing both structured entry chunks and raw `source_markdown` proxy document chunks.

---

## 6. Data Flow

```
Upload (file)
  → extract_text()
  → save_proxy_markdown()
  → structurer.structure()      [GPT-4o-mini]
  → store.upsert_spec()
  → engine.index_house()        [Turbovec: structured + source_markdown chunks]
  → graph_engine.rebuild()      [NetworkX DiGraph from DB]

MCP search_assertions(query)
  → _embed(query)
  → index.query(...)
  → _rerank(matches)                    [filters out non-APPROVED/LOCKED entries unless include_unapproved=True]
  → GroundingResponse

MCP get_graph_connections(domain_id)
  → graph_engine.get_connections()

MCP generate_artifact(skill_id, domain_id)
  → store.get_assertions()   [ALL entries]
  → store.get_personas()        [ALL audiences]
  → _build_context()
  → LLM prompt generation
```

---

## 7. Tech Stack

| Layer | Technology |
|---|---|
| MCP Server | FastMCP (SSE transport) |
| Web API | FastAPI |
| ORM / DB | SQLAlchemy + SQLite / PostgreSQL |
| Vector DB | Turbovec (local, in-process) |
| Graph | NetworkX |

---

## 8. Constraints

- Eventual consistency: Knowledge graph is rebuilt from DB on server start.
- Quantization: Turbovec uses local 4-bit embeddings.

---

## 9. Quality Criteria

A generated artifact is considered "grounded" if:
- All approved assertions from the active spec were available (no truncation)
- Full audience context was included in prompt
- No vector approximation path was used for governance-critical content (use graph mode)

---

## 10. Planned Milestones

### v0.8 — Visual Artifact Engine
- Design System Foundation: brand settings, templates registry.
- Canvas Renderer: Fabric.js, Reveal.js, Penpot integrations.

### v0.9 — Retrieval & Tiering
- Alignment Scoring: continuous scoring and drift reports; soft vs. hard conflict classification; third-party export interface.
- Suggestion Workflows: suggestion routing, element-level RBAC (4 permission levels), and conflict review set routing.
- Deliverable custom inputs: brand voice tonal sliders and controlled vocabulary checks.
- Temporary priority messaging layer.
- "Gold Standard" content designation.
- Content Tiering: Tier 1 Locked / Tier 2 Structured / Tier 3 Grounded generation contract per entry, enforced in generation and retrieval routing (see §4.9).
- Content SLA: per-domain review cadence, trigger-event review windows, breach notifications, SLA dashboard (see §4.10).
- DRI Ownership: named accountable individual per entry and domain, with transfer flow and accountability view.
- Dual Output: citation-marked review copy + clean deliverable on every generated artifact (see §4.11).
- Query Audit Log: who queried, what was returned, when — admin-accessible with export (see §4.12).

### v1.0 — Cross-Department Graph & Dependency Graphs
- Nested child specs with 4 inheritance relationship types.
- Bindings layer mapping live elements to output deliverables.
- Product Graph: core specs, API rules, compliance schemas.
- Domain Dependencies: Graph dependency tracking (`INFORMS` / `DEPENDS_ON`) and cascade drift updates.
- Graph Health view for administrators.
- Content CI/CD Pipeline: gated Draft→Approved promotion — validate → test (golden dataset) → merge → propagate → audit; failed validation blocks promotion.
- Golden Query Dataset & Retrieval Benchmarking: per-domain benchmark queries, precision/recall baselines, corpus-health monitoring.
- Identity-Scoped Retrieval: OIDC/SSO login with per-user retrieval scoping (pulled forward from v1.6) — embargoed/pre-announcement content never surfaces outside its authorized audience.

### v1.1 — Agentic Graph Navigation
- Specialized functional agents (governance, brand voice, narrative structure).
- Graph Navigator natural language dashboard assistant.
- Ingestion upgrades: decks, spreadsheets, transcripts, voice memos, unstructured notes with placement recommendations.
- Render-mode tagging on ingested assets: `render_whole` (insert verbatim as authored) vs `read_as_content` (parse as structured input).
- Industry/segment as a first-class variant dimension on assertions and audiences (audience × channel × industry).
- Deck indexing & presentation assembly: index existing approved decks, surface relevant slides on query, assemble new deck outlines from approved content.
- Audio/video indexing: transcript segment classification at ingest, timestamped moment retrieval.
- Intent-based routing & model selection: classify query intent, route to the appropriate model tier and skill (or skill chain) automatically.
- Localization skill: adapt tone, cultural references, and market context for regional output, with brand-voice QA gate.
- Value telemetry: acceptance signals (saved/exported/published) per artifact and value reporting (hours saved × executions × acceptance rate).
