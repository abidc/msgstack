# MsgStack — Roadmap

**Last Updated:** April 2026

This roadmap reflects current state and planned direction. Items are grouped by milestone, not calendar quarter — sequencing depends on usage feedback and priority shifts.

---

## Current State — v0.6 (April 2026)

**Shipped (Milestones v0.1 - v0.6):**
- ✅ FastMCP server with 20+ grounding + artifact tools
- ✅ FastAPI admin UI with full Frameworks/Skills/Workspaces management
- ✅ **Advanced Upload Pipeline:** PDF/DOCX/TXT → Multi-chunk structuring → Vector index
- ✅ **Preview & Confirm:** Extract and review structured messaging before committing to DB
- ✅ **LLM Persona Parsing:** Robust JSON extraction replacing regex state machines
- ✅ **Hybrid Search:** Vector + keyword overlap reranking with `min_confidence` control
- ✅ **Versioning:** Snapshot system for history, diffing, and restoration
- ✅ **Artifact Pro:** Generate 12+ artifact types with DOCX/PDF export and visual previews
- ✅ **Artifact History:** Persistent storage and retrieval of all generated content
- ✅ **Multi-Tenancy:** Workspace-scoped frameworks, API keys, and Pinecone namespaces
- ✅ **Production Auth:** Scoped API key authentication (`read`/`write`/`admin`)
- ✅ **Operations:** Structured logging, rate limiting, and workspace token budgets
- ✅ **Infrastructure:** Full PostgreSQL support and Docker Compose deployment
- ✅ **Test Suite:** Comprehensive unit and integration tests (extraction, structure, store)
- ✅ **Jinja2 UI Architecture:** Admin UI migrated from single HTML to `base.html` + `dashboard.html` template system
- ✅ **Dark Artifact Visual Page:** `/artifact/one_pager/{id}` renders with dashboard-matching dark theme, color-coded message sections, persona cards, and PDF export
- ✅ **Tabbed House Detail:** Framework detail view with Overview (editable), Messages (color-coded by section type, drag-to-reorder), and Personas tabs
- ✅ **Skill Context Inputs:** Skills that require pre-generation context (competitor name for battlecard, funnel stage for email, topic for blog post, etc.) surface input fields in the UI before generation; MCP tool proactively asks for missing required context
- ✅ **SPA Routing:** Page refresh from any app section works correctly via FastAPI catch-all route + client-side `initRouting()`
- ✅ **Logo Navigation:** MsgStack logo always returns to dashboard

**Known gaps:**
- OIDC/OAuth login not yet implemented (API key auth only)
- Workspace "invites" still manual via API
- Paged.js / Satori visual pipeline not yet operational

---

## v0.2 — Hardening & Quality

**Goal:** Make the system reliable enough for regular daily use without workarounds.

### Upload Pipeline Reliability
- [x] Show spinner and estimated time during LLM structuring
- [x] Retry with exponential backoff on OpenAI timeout
- [x] Show a diff/preview of structured sections before saving
- [x] Handle very large documents (>24k chars) with multi-chunk structuring + merge step
- [x] Surface raw extraction errors clearly in the UI rather than silent failures

### Re-indexing
- [x] "Re-index" button per framework in the Frameworks UI
- [x] "Index All" button in the dashboard
- [x] Show Pinecone index status per framework (indexed / not indexed / stale)

### Persona Parser
- [x] Rewrite `_parse_personas` to use structured JSON output from the LLM

### Search Quality
- [x] Add `know_your_market` as its own section type queryable via `search_messaging`
- [x] Improve `_rerank()` — implemented blending of vector score with token overlap
- [x] Add `min_confidence` parameter to `search_messaging` — return warning if results below threshold

### Error Handling
- [x] `/api/extract` returns structured error JSON
- [x] Wrap all Pinecone calls in consistent try/except with logging
- [x] Add request logging with timing for all `/api/*` endpoints

### Test Coverage
- [x] Unit tests for `extract.py`
- [x] Unit tests for `structure.py`
- [x] Integration tests for `/api/extract` and `search_messaging`

---

## v0.3 — Framework Authoring & Collaboration

**Goal:** Make it easier for marketing teams to build high-quality frameworks.

### In-UI Framework Editor
- [x] Inline editing of all MessageHouse fields
- [x] Add/edit/delete individual key messages directly in the UI
- [x] Drag to reorder key messages within a section type
- [x] Bulk import key messages from CSV or paste-from-spreadsheet

### AI-Assisted Authoring
- [x] "Generate missing section" for all required fields
- [x] "Improve" button per key message
- [x] "Generate persona" from a job title input
- [x] "Check tone" — analyze a message against the framework's `brand_personality`

### Framework Versioning
- [x] Snapshot a framework before making changes (store as JSON blob)
- [x] View snapshot history per framework
- [x] Restore from snapshot
- [x] Show diff between current and last snapshot

---

## v0.4 — Artifact Quality & Delivery

**Goal:** Make generated artifacts output-ready, not just drafts.

### Artifact Preview & Editing
- [x] Copy-to-clipboard per section
- [x] Download artifact as DOCX or PDF
- [x] Automatic "Visual Version" links for every generated artifact

### Visual Artifact Improvements
- [x] Add `battlecard` visual artifact type
- [x] Add `email_sequence` visual type
- [x] Print-optimized CSS for one-pager (`@media print`)
- [x] Light mode / dark mode toggle on artifact pages

### New Skill Templates
- [x] 12+ total skills including `talk_track`, `objection_handler`, `event_brief`, `executive_summary`, `partner_brief`

### Artifact History
- [x] Save generated artifacts to DB with timestamp and skill used
- [x] View artifact history per framework
- [x] Re-open and re-generate from history entry

---

## v0.5 — Auth, Multi-Tenancy, and Production Readiness

**Goal:** Make MsgStack deployable as a shared team service.

### Authentication
- [x] API key authentication for `/api/*` endpoints and MCP tools
- [x] Per-key scopes: read-only (search + generate) vs read-write (create + delete)

### Multi-Tenancy
- [x] Workspace concept: separate sets of frameworks, skills, and uploads per workspace
- [x] Workspace-scoped Pinecone namespaces

### Production Infrastructure
- [x] Docker Compose config for full stack deployment
- [x] PostgreSQL support alongside SQLite
- [x] Persistent session storage (DB-backed)
- [x] Health check endpoint at `/health`
- [x] Structured logging (JSON) with metrics tracking

---

## v0.6 — Governance & Marketing Operations

**Goal:** Bridge the gap between AI generation and marketing department workflows using a "High-Impact" architecture (HTMX + Paged.js + Satori).

### High-Impact Artifact Generation
- [x] **Jinja2 + HTMX UI Architecture:** Admin UI refactored to Jinja2 templates (`base.html`, `dashboard.html`) with HTMX for dynamic interactions.
- [x] **Dark-Themed Visual Artifact Page:** `artifact_visual.html` template with dark dashboard aesthetic, color-coded message sections, persona cards, print/PDF export.
- [x] **Skill Context Inputs:** Dynamic pre-generation context fields in the UI (competitor for battlecard, stage for email, topic for blog post); validation before generation runs.
- [x] **MCP Context Validation:** `build_artifact` MCP tool proactively requests missing required context instead of returning a cryptic error.
- [x] **SPA Routing Robustness:** Page refresh from any section works; catch-all FastAPI route + `initRouting()` client-side routing.
- [x] **Logo Navigation:** Clicking the MsgStack logo returns to the dashboard from any section.
- [ ] **Print-First Documents (Paged.js):** Professional typeset PDFs for One-Pagers and Battlecards with real margins, page numbers, and bleed.
- [ ] **Design-as-Code Visuals (Satori):** Generate high-fidelity PNG social cards and email headers using the Satori WASM engine + `resvg-python`.
- [ ] **Inline Polish Editor:** Rich-text editor (TinyMCE/Quill) in the UI to tweak AI drafts before final save.

### Messaging Governance
- [ ] **Approval Workflow:** Mark Key Messages as `Draft` or `Approved` (Grounding search prioritizes `Approved`).
- [ ] **Locking:** Prevent editing of "Core Messaging" once approved by department heads.
- [ ] **Artifact Status:** Lifecycle tracking for generated docs: `Draft` → `Internal Review` → `Approved`.

### Maintenance & Lifecycle
- [ ] **Staleness Alerts:** "Last Reviewed" timestamp per framework; flag frameworks older than 90 days.
- [ ] **Sync Reminders:** Dashboard widget showing which brand frameworks need refreshing.
- [ ] **Review Trail:** Log of who reviewed/approved messaging updates and when.

### The "Feedback Loop"
- [ ] **Content Ratings:** Rate generated artifacts (1-5 stars) or "Good/Bad" tags.
- [ ] **Self-Correction:** Boost search relevance for messaging chunks used in "High Rated" artifacts.
- [ ] **Usage Heatmap:** See which parts of the message house are being used most vs ignored.

### Last-Mile Design & Hand-off
- [ ] **Editable Export Pro:** Export DOCX that preserves visual hierarchy and styling for easier design hand-off.
- [ ] **Push to Tooling:** "Export to Slides" (via Google Slides API) or placeholder Figma JSON export.

---

## v0.7 — Hybrid Knowledge Graph + Vector RAG

**Goal:** Introduce a two-layer retrieval architecture that separates semantic search from deterministic governance. Vector search finds *thematically relevant* messaging; graph traversal returns *verbatim approved* messaging via deterministic relationship queries. Taglines, approved headlines, and locked proof points should be retrieved exactly — not approximated by nearest-neighbor search.

### Knowledge Graph Integration
- [ ] **Graph Schema:** MessageHouse, KeyMessage, Persona, Channel nodes with typed relationships
- [ ] **Relationship Mapping:** CONTAINS (House→Message), TARGETS (House→Persona), APPLIES_TO (Message→Channel), ADDRESSES (Message→Persona)
- [ ] **Graph Store:** SQLite-based adjacency tables as initial implementation; Neo4j migration path for scale
- [ ] **Hybrid Query Routing:** Route queries between vector (exploratory), graph (governance), and keyword (filtered) paths based on query type and message lock status

### Multimodal Document Processing
- [ ] **Vision Model Fallback:** Detect pages with high graphical element ratio (>40% images) and route to GPT-4V for layout extraction
- [ ] **Unified Indexing:** Route text chunks to Pinecone; store entity relationships in the graph store simultaneously on ingest

### Graph-Enhanced Search
- [ ] **Exploratory Path:** Vector search first, then graph traversal to surface contextually related messages
- [ ] **Governance Path:** Direct graph traversal for deterministic retrieval of approved/locked messages — bypasses vector approximation
- [ ] **Path Discovery:** Find related messages through persona → message → channel relationship chains

### Multi-Content-Type Foundation
- [ ] **DocumentType Discriminator:** Add `document_type` column to `message_houses` table with a `DocumentType` enum: `message_house`, `brand_guide`, `competitive_brief`, `corp_narrative`, `persona_library`. Backward-compatible — all existing rows default to `message_house`.
- [ ] **SectionType Expansion:** Extend `SectionType` enum with content-type-specific variants: `brand_voice`, `style_rule`, `word_list`, `narrative_pillar`, `company_value`, `founding_story`, `competitor_strength`, `competitor_weakness`, `competitive_response`, `persona_detail`.
- [ ] **Channel as DB Entity:** Promote `Channel` from a code enum to a `ChannelModel` SQLAlchemy table with full CRUD endpoints. Seed with defaults: `all`, `email`, `linkedin`, `twitter`, `paid_ads`, `landing_page`, `sales_deck`. Enables user-defined channels without code changes.

---

## v0.8 — Advanced Graph Operations & Visualization

**Goal:** Enable graph-powered insights and visual exploration of messaging relationships.

### Graph Visualization
- [ ] **Knowledge Graph Explorer:** Interactive UI to visualize MessageHouse → KeyMessage → Persona relationships
- [ ] **Relationship Browser:** Click through CONTAINS/TARGETS/APPLIES_TO/ADDRESSES edges
- [ ] **Path Finder:** Visualize paths between entities (e.g., "how does this message reach this persona?")

### Graph-Powered Queries
- [ ] **Persona Coverage Analysis:** Which messages address which personas? Identify gaps.
- [ ] **Channel Reachability:** Which channels can a message reach through APPLIES_TO relationships?
- [ ] **Cross-Framework Comparison:** Compare messaging relationships across multiple houses

### Graph Maintenance
- [ ] **Sync Pipeline:** Keep graph in sync with SQLite/PostgreSQL changes
- [ ] **Conflict Resolution:** Handle concurrent edits to graph entities
- [ ] **Backup & Restore:** Include graph data in snapshot system

### Cross-Document Intelligence
- [ ] **GroundingCollection:** Bundle multiple documents (e.g., brand guide + message house + persona library) into a named collection. MCP tools can target the entire collection for search and artifact generation.
- [ ] **INFORMS Edge:** `(GroundingDocument) -[:INFORMS]-> (GroundingDocument)` cross-document relationship. Graph traversal can follow `INFORMS` edges to surface the source-of-truth document behind a message (e.g., "this tagline is governed by the brand guide").

---

## v1.0 — Platform & Ecosystem

**Goal:** MsgStack as a platform other tools and workflows integrate with.

### Integrations
- [ ] **Notion connector** — Sync frameworks to/from Notion pages
- [ ] **Google Drive connector** — Watch a folder for new/updated source documents
- [ ] **Slack app** — Query messaging and generate artifacts via Slack command
- [ ] **HubSpot / Salesforce** — Push approved messaging to CRM as snippet library

### Advanced Search & Governance
- [ ] **Cross-framework search** — "What do all our product teams say about security?"
- [ ] **Gap analysis** — "Which frameworks lack proof points for the CISO persona?"
- [ ] **Audit Trail** — Comprehensive changelog of all framework modifications.

---

## Backlog (Unscheduled)

- Multi-LLM support (Anthropic Claude, Gemini)
- Custom embedding models (local Ollama)
- Import from PPTX
- CLI tool (`msgstack search "..."`)
- VS Code extension for inline messaging suggestions

---

## What We're Not Building

- A full CMS or social media scheduling tool
- A CRM replacement
- Real-time chat/collaboration

MsgStack is messaging infrastructure — the data layer and search/generation API.
