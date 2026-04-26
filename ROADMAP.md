# MsgStack — Roadmap

**Last Updated:** April 2026

This roadmap reflects current state and planned direction. Items are grouped by milestone, not calendar quarter — sequencing depends on usage feedback and priority shifts.

---

## Current State — v0.1 (April 2026)

**Shipped:**
- ✅ FastMCP server with 15+ grounding + artifact tools (SSE transport)
- ✅ FastAPI admin UI (frameworks, upload, skills, artifact generator, seed)
- ✅ Document ingestion pipeline: PDF/DOCX/TXT → LLM structuring → SQLite + Pinecone
- ✅ Hybrid vector + metadata search (Pinecone + OpenAI embeddings)
- ✅ 7 artifact skill templates (one-pager, LinkedIn, email, battlecard, press release, blog, FAQ)
- ✅ Standalone HTML visual artifacts (one-pager, social posts, email sequence)
- ✅ Framework completeness scoring (0-100) with missing section detection
- ✅ Know Your Market pre-section extraction and display
- ✅ Use Case (`use_case`) as a first-class message section type
- ✅ Single-step upload → extract → structure → index flow
- ✅ Skill template CRUD via admin UI
- ✅ Session tracking (active house, used chunks, confidence)
- ✅ Cloudflare tunnel deployment at `mcp.abidc.dev`
- ✅ Graceful Pinecone fallback to keyword search

**Known gaps:**
- No auth on any endpoint (open to anyone with URL)
- Session state lost on server restart
- SQLite only — not concurrent-write safe
- No re-index trigger from UI (requires curl)
- Visual artifacts are static HTML with no interactivity
- `_parse_personas` is a fragile state machine; complex persona sections may parse incorrectly
- No test suite

---

## v0.2 — Hardening & Quality

**Goal:** Make the system reliable enough for regular daily use without workarounds.

### Upload Pipeline Reliability
- [ ] Show spinner and estimated time during LLM structuring (currently silent after text preview)
- [ ] Retry with exponential backoff on OpenAI timeout
- [ ] Show a diff/preview of structured sections before saving — let user confirm or edit before committing to DB
- [ ] Handle very large documents (>24k chars) with multi-chunk structuring + merge step
- [ ] Surface raw extraction errors clearly in the UI rather than silent failures

### Re-indexing
- [ ] "Re-index" button per framework in the Frameworks UI (currently curl-only)
- [ ] "Index All" button in the dashboard
- [ ] Show Pinecone index status per framework (indexed / not indexed / stale)

### Persona Parser
- [ ] Rewrite `_parse_personas` to use structured JSON output from the LLM instead of the current regex state machine — eliminates parsing bugs for complex persona sections

### Search Quality
- [ ] Add `know_your_market` as its own section type queryable via `search_messaging`
- [ ] Improve `_rerank()` — currently a pass-through; implement at minimum a BM25 or keyword-overlap reranking pass
- [ ] Add `min_confidence` parameter to `search_messaging` — return warning if results below threshold

### Error Handling
- [ ] `/api/extract` should return structured error JSON (not bare 500) with which stage failed and why
- [ ] Wrap all Pinecone calls in consistent try/except with logging
- [ ] Add request logging with timing for all `/api/*` endpoints

### Test Coverage
- [ ] Unit tests for `extract.py` (all three file types)
- [ ] Unit tests for `structure._parse_markdown()` (canonical format + edge cases)
- [ ] Unit tests for `structure._parse_key_messages()` with Priority-suffix headers
- [ ] Integration test for `/api/extract` with sample DOCX
- [ ] Integration test for `search_messaging` with mock Pinecone

---

## v0.3 — Framework Authoring & Collaboration

**Goal:** Make it easier for marketing teams to build high-quality frameworks, not just upload documents.

### In-UI Framework Editor
- [ ] Inline editing of all MessageHouse fields (currently read-only in the Frameworks tab)
- [ ] Add/edit/delete individual key messages directly in the UI
- [ ] Drag to reorder key messages within a section type
- [ ] Bulk import key messages from CSV or paste-from-spreadsheet

### AI-Assisted Authoring
- [ ] "Generate missing section" for all required fields (not just post-upload)
- [ ] "Improve" button per key message — suggest a stronger version via LLM
- [ ] "Generate persona" from a job title input
- [ ] "Check tone" — analyze a message against the framework's `brand_personality` and flag mismatches

### Framework Versioning
- [ ] Snapshot a framework before making changes (store as JSON blob)
- [ ] View snapshot history per framework
- [ ] Restore from snapshot
- [ ] Show diff between current and last snapshot

### Completeness Improvements
- [ ] Completeness score visible in framework list (badge/progress bar per row)
- [ ] "Fix it" quick actions from the completeness checker — jump directly to missing section
- [ ] Completion milestone notifications ("Your CPG framework is now 90% complete")

### Key Message Variants
- [ ] UI for adding channel-specific variants per message (LinkedIn, email, paid, Twitter)
- [ ] Variant preview switcher — toggle between channel versions inline
- [ ] Auto-generate channel variant via LLM from the base message

---

## v0.4 — Artifact Quality & Delivery

**Goal:** Make generated artifacts output-ready, not just drafts.

### Artifact Preview & Editing
- [ ] Inline editing of generated artifact sections before saving/exporting
- [ ] Regenerate individual sections without regenerating the whole artifact
- [ ] Copy-to-clipboard per section
- [ ] Download artifact as DOCX or PDF

### Visual Artifact Improvements
- [ ] Add `battlecard` visual artifact type (competitive comparison table layout)
- [ ] Add `email_sequence` visual type (3-panel funnel view)
- [ ] Print-optimized CSS for one-pager (`@media print`)
- [ ] Light mode / dark mode toggle on artifact pages

### New Skill Templates
- [ ] `talk_track` — Sales call talk track with stage-specific talking points
- [ ] `objection_handler` — Full objection/rebuttal reference card
- [ ] `event_brief` — Conference/event messaging brief
- [ ] `executive_summary` — C-level briefing format
- [ ] `partner_brief` — Channel partner messaging enablement sheet

### Artifact History
- [ ] Save generated artifacts to DB with timestamp and skill used
- [ ] View artifact history per framework
- [ ] Re-open and re-generate from history entry

---

## v0.5 — Auth, Multi-Tenancy, and Production Readiness

**Goal:** Make MsgStack deployable as a shared team service, not just a personal tool.

### Authentication
- [ ] API key authentication for `/api/*` endpoints and MCP tools
- [ ] Optional OIDC/OAuth login for the admin UI (Google, Microsoft)
- [ ] Per-key scopes: read-only (search + generate) vs read-write (create + delete)

### Multi-Tenancy
- [ ] Workspace concept: separate sets of frameworks, skills, and uploads per workspace
- [ ] Workspace-scoped Pinecone namespaces
- [ ] Invite-based workspace membership

### Production Infrastructure
- [ ] Docker Compose config for full stack deployment
- [ ] PostgreSQL support alongside SQLite (configurable via env var)
- [ ] Persistent session storage (Redis or DB-backed)
- [ ] Health check endpoint at `/health`
- [ ] Structured logging (JSON) with configurable log level
- [ ] Metrics: request count, latency, LLM token usage per endpoint

### Rate Limiting & Cost Controls
- [ ] Per-endpoint rate limiting (especially `/api/extract` and `/api/generate`)
- [ ] Token usage tracking per generation call
- [ ] Cost estimate surfaced in the UI before running LLM operations
- [ ] Max token budget configurable per workspace

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
