# MsgStack — Roadmap

**Last Updated:** April 2026

This roadmap reflects current state and planned direction. Items are grouped by milestone, not calendar quarter — sequencing depends on usage feedback and priority shifts.

---

## Current State — v0.5 (April 2026)

**Shipped (Milestones v0.1 - v0.5):**
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

**Known gaps:**
- OIDC/OAuth login not yet implemented (API key auth only)
- Workspace "invites" still manual via API
- Static visual artifacts (interactive React-based artifacts in backlog)

---

## v0.2 — Hardening & Quality

**Goal:** Make the system reliable enough for regular daily use without workarounds.

### Upload Pipeline Reliability
- [x] Show spinner and estimated time during LLM structuring (Backend supports preview/confirm flow)
- [x] Retry with exponential backoff on OpenAI timeout
- [x] Show a diff/preview of structured sections before saving — let user confirm or edit before committing to DB
- [x] Handle very large documents (>24k chars) with multi-chunk structuring + merge step
- [x] Surface raw extraction errors clearly in the UI rather than silent failures

### Re-indexing
- [x] "Re-index" button per framework in the Frameworks UI
- [x] "Index All" button in the dashboard
- [x] Show Pinecone index status per framework (indexed / not indexed / stale)

### Persona Parser
- [x] Rewrite `_parse_personas` to use structured JSON output from the LLM instead of the current regex state machine

### Search Quality
- [x] Add `know_your_market` as its own section type queryable via `search_messaging`
- [x] Improve `_rerank()` — implemented blending of vector score with token overlap
- [x] Add `min_confidence` parameter to `search_messaging` — return warning if results below threshold

### Error Handling
- [x] `/api/extract` returns structured error JSON with which stage failed and why
- [x] Wrap all Pinecone calls in consistent try/except with logging
- [x] Add request logging with timing for all `/api/*` endpoints

### Test Coverage
- [x] Unit tests for `extract.py` (all three file types)
- [x] Unit tests for `structure._parse_markdown()` (canonical format + edge cases)
- [x] Unit tests for `structure._parse_key_messages()` with Priority-suffix headers
- [x] Integration test for `/api/extract` with sample DOCX
- [x] Integration test for `search_messaging` with mock Pinecone

---

## v0.3 — Framework Authoring & Collaboration

**Goal:** Make it easier for marketing teams to build high-quality frameworks, not just upload documents.

### In-UI Framework Editor
- [x] Inline editing of all MessageHouse fields
- [x] Add/edit/delete individual key messages directly in the UI
- [x] Drag to reorder key messages within a section type
- [x] Bulk import key messages from CSV or paste-from-spreadsheet

### AI-Assisted Authoring
- [x] "Generate missing section" for all required fields
- [x] "Improve" button per key message — suggest a stronger version via LLM
- [x] "Generate persona" from a job title input
- [ ] "Check tone" — analyze a message against the framework's `brand_personality`

### Framework Versioning
- [x] Snapshot a framework before making changes (store as JSON blob)
- [x] View snapshot history per framework
- [x] Restore from snapshot
- [x] Show diff between current and last snapshot

### Completeness Improvements
- [x] Completeness score visible in framework list (badge/progress bar per row)
- [ ] "Fix it" quick actions from the completeness checker — jump directly to missing section
- [ ] Completion milestone notifications

### Key Message Variants
- [x] UI for adding channel-specific variants per message (LinkedIn, email, paid, Twitter)
- [x] Variant preview switcher — toggle between channel versions inline
- [x] Auto-generate channel variant via LLM from the base message

---

## v0.4 — Artifact Quality & Delivery

**Goal:** Make generated artifacts output-ready, not just drafts.

### Artifact Preview & Editing
- [ ] Inline editing of generated artifact sections before saving/exporting
- [ ] Regenerate individual sections without regenerating the whole artifact
- [x] Copy-to-clipboard per section (Frontend supported)
- [x] Download artifact as DOCX or PDF

### Visual Artifact Improvements
- [x] Add `battlecard` visual artifact type (competitive comparison table layout)
- [x] Add `email_sequence` visual type (3-panel funnel view)
- [x] Print-optimized CSS for one-pager (`@media print`)
- [x] Light mode / dark mode toggle on artifact pages

### New Skill Templates
- [x] `talk_track` — Sales call talk track with stage-specific talking points
- [x] `objection_handler` — Full objection/rebuttal reference card
- [x] `event_brief` — Conference/event messaging brief
- [x] `executive_summary` — C-level briefing format
- [x] `partner_brief` — Channel partner messaging enablement sheet

### Artifact History
- [x] Save generated artifacts to DB with timestamp and skill used
- [x] View artifact history per framework
- [x] Re-open and re-generate from history entry

---

## v0.5 — Auth, Multi-Tenancy, and Production Readiness

**Goal:** Make MsgStack deployable as a shared team service, not just a personal tool.

### Authentication
- [x] API key authentication for `/api/*` endpoints and MCP tools
- [ ] Optional OIDC/OAuth login for the admin UI (Google, Microsoft)
- [x] Per-key scopes: read-only (search + generate) vs read-write (create + delete)

### Multi-Tenancy
- [x] Workspace concept: separate sets of frameworks, skills, and uploads per workspace
- [x] Workspace-scoped Pinecone namespaces
- [ ] Invite-based workspace membership

### Production Infrastructure
- [x] Docker Compose config for full stack deployment
- [x] PostgreSQL support alongside SQLite (configurable via env var)
- [x] Persistent session storage (DB-backed)
- [x] Health check endpoint at `/health`
- [x] Structured logging (JSON) with configurable log level
- [x] Metrics: request count, latency, LLM token usage per endpoint

### Rate Limiting & Cost Controls
- [x] Per-endpoint rate limiting (especially `/api/extract` and `/api/generate`)
- [x] Token usage tracking per generation call
- [x] Cost estimate surfaced in the UI before running LLM operations
- [x] Max token budget configurable per workspace

---

## v1.0 — Platform & Ecosystem

**Goal:** MsgStack as a platform other tools and workflows integrate with.

### Integrations
- [ ] **Notion connector** — Sync frameworks to/from Notion pages
- [ ] **Google Drive connector** — Watch a folder for new/updated source documents, auto-ingest
- [ ] **Slack app** — Query messaging and generate artifacts via Slack command
- [ ] **HubSpot / Salesforce** — Push approved messaging to CRM as snippet library
- [ ] **Zapier / n8n webhook trigger** — Fire on framework create/update

### Analytics
- [ ] Artifact generation tracking (which skills, which frameworks, how often)
- [ ] Search analytics (most searched terms, frameworks with highest recall)
- [ ] Framework usage report (which houses are being actively grounded vs ignored)
- [ ] Messaging effectiveness scoring (correlate content use with pipeline/conversion data)

### Advanced Search
- [ ] Cross-framework search and synthesis — "What do all our product teams say about security?"
- [ ] Similarity search — "Find messages similar to this copy I wrote"
- [ ] Gap analysis — "Which frameworks lack proof points for the CISO persona?"

### Framework Governance
- [ ] Approval workflow — framework changes require review before publish
- [ ] Expiration dates on key messages — flag stale proof points past a date
- [ ] Owner assignment per framework with notification on completeness drop
- [ ] Changelog / audit trail of who changed what and when

---

## Backlog (Unscheduled)

These are real ideas that don't have a milestone yet:

- Multi-LLM support (Anthropic Claude, Gemini) for structuring and generation
- Custom embedding models (local Ollama, Cohere)
- Import from PPTX (parse slides as source documents)
- Export all frameworks to a single PDF "messaging book"
- Framework merge — combine two frameworks into one
- Message quality scoring via LLM (benefit-led? specific? credible?)
- Localization / translation of key messages into other languages
- A/B message variant tracking (send different variants, track which performs)
- CLI tool (`msgstack search "..."`, `msgstack generate one_pager ...`)
- VS Code extension for inline messaging suggestions while writing

---

## What We're Not Building

- A full CMS or content management platform
- A social media scheduling tool
- A CRM replacement
- Real-time chat or collaboration features (comments, @mentions)
- A no-code workflow builder

MsgStack is messaging infrastructure — the data layer and search/generation API. Content publishing, scheduling, and distribution belong in downstream tools that integrate with MsgStack.
