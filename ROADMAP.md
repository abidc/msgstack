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
- ✅ **Skill Context Inputs:** Skills that require pre-generation context surface input fields in the UI before generation; MCP tool proactively asks for missing required context
- ✅ **SPA Routing:** Page refresh from any app section works correctly via FastAPI catch-all + `initRouting()`
- ✅ **Multi-Content-Type:** `document_type` discriminator on message houses (`message_house`, `brand_guide`, `competitive_brief`, `corp_narrative`, `persona_library`) with color-coded badges in the UI
- ✅ **Knowledge Graph Engine:** NetworkX DiGraph built from SQLite — deterministic retrieval via typed entity relationships (`graph.py` fully implemented)
- ✅ **Graph Explorer UI:** Interactive Cytoscape.js canvas in the admin UI with node filtering, relationship browser, and detail panel
- ✅ **Extended Graph Entities:** MessagingPillar, PainPoint, BuyingTrigger, and Objection promoted to first-class graph nodes with typed edges (HAS_PAIN_POINT, HAS_TRIGGER, HAS_OBJECTION, RESOLVES)
- ✅ **`get_graph_connections` MCP Tool:** Deterministic graph traversal tool for AI assistants — returns verbatim approved content via typed relationships, bypassing vector approximation
- ✅ **Full-Context Grounding:** `generate_artifact` now loads ALL key messages (grouped by section type, sorted by priority) and ALL personas (with pain points, buying triggers, and objections) — no arbitrary caps; full structured grounding block prepended to every artifact prompt with explicit grounding contract
- ✅ **Grounding Guardrails:** `list_message_houses` response includes `_next_step` instruction directing AI agents to call `generate_artifact` rather than writing content from metadata alone

**Known gaps:**
- OIDC/OAuth login not yet implemented (API key auth only)
- Workspace "invites" still manual via API
- Visual artifact rendering (Fabric.js, reveal.js, Penpot) not yet implemented — planned v0.8
- Channel still a code enum (DB entity promotion not yet done)
- Multimodal/vision model fallback not yet implemented

---

## v0.7 — Knowledge Graph Completion

**Goal:** Complete the remaining graph and governance items from the original v0.7 scope.

### Channel as a First-Class Entity
- [ ] **ChannelModel DB table:** Promote `Channel` from a code enum to a SQLAlchemy table with full CRUD endpoints
- [ ] **Seed defaults:** `all`, `email`, `linkedin`, `twitter`, `paid_ads`, `landing_page`, `sales_deck`
- [ ] **User-defined channels:** Create custom channels (e.g., `partner_portal`, `in-app`) via UI without code changes
- [ ] **Graph node upgrade:** Channel nodes in graph engine backed by DB rows with full metadata

### Graph Governance
- [ ] **Approval Workflow:** Mark Key Messages as `Draft` or `Approved`; grounding search prioritizes `Approved`
- [ ] **Locking:** Prevent editing of "Core Messaging" once approved by department heads
- [ ] **Artifact Status:** Lifecycle tracking: `Draft` → `Internal Review` → `Approved`
- [ ] **Staleness Alerts:** "Last Reviewed" timestamp per framework; flag frameworks older than 90 days
- [ ] **Review Trail:** Log of who reviewed/approved messaging updates and when

### Feedback Loop
- [ ] **Content Ratings:** Rate generated artifacts (1-5 stars) or "Good/Bad" tags
- [ ] **Self-Correction:** Boost search relevance for messaging chunks used in "High Rated" artifacts
- [ ] **Usage Heatmap:** See which parts of the message house are being used most vs ignored

### Last-Mile Design
- [ ] **Print-First Documents (Paged.js):** Professional typeset PDFs with real margins, page numbers, and bleed — see v0.8 for the full visual artifact engine

---

## v0.8 — Visual Artifact Engine (Fabric.js + reveal.js + Penpot)

**Goal:** Replace server-rendered HTML artifact pages with a browser-side design engine that supports real graphic design capabilities — image and logo insertion, layered layouts, custom typography, and export to PNG/PDF. Three complementary rendering paths cover every artifact class.

### Fabric.js — Visual & Graphic Artifacts
Canvas-based design engine for one-pagers, battlecards, social cards, and any artifact that needs graphic design fidelity. The LLM generates a **design JSON spec** (not HTML) describing the layout tree; the browser renders it as a Fabric.js canvas. Users can interactively edit before exporting.

- [ ] **Design JSON spec schema:** Define the artifact layout format — zones (hero, body, sidebar, footer), text blocks with font/size/color, image placeholders with type (`logo`, `hero_image`, `icon`), shape layers, brand color tokens
- [ ] **Fabric.js canvas renderer:** Deserialize the design JSON into Fabric.js objects; render all element types (text, image, rect, SVG) with layer ordering
- [ ] **Logo & image insertion:** `fabric.Image.fromURL()` support with drag-and-drop replace; accept URL, file upload, or base64 — no server round-trip
- [ ] **Per-artifact-type templates:** Pre-designed Fabric.js templates for `one_pager`, `battlecard`, `social_card`, `event_brief` — each with defined content zones and brand styling
- [ ] **Export pipeline:** PNG via `canvas.toDataURL()`; PDF via jsPDF wrapper preserving vector text where possible; SVG export for design hand-off
- [ ] **Brand token system:** Workspace-level color palette and font settings applied across all Fabric.js templates automatically
- [ ] **`generate_fabric_artifact` MCP tool:** Returns design JSON spec grounded in the message house; client renders it in the browser

### reveal.js — Presentations & Slide Decks
HTML-based presentation engine for sales decks, event presentations, partner briefings, and executive readouts. The LLM generates the slide HTML structure; reveal.js handles rendering, transitions, and speaker notes.

- [ ] **Slide skill templates:** New skill types — `sales_deck`, `event_presentation`, `executive_readout` — with structured slide schemas (title, agenda, value prop, proof point, CTA, appendix)
- [ ] **LLM slide generation:** `generate_artifact(skill_id="sales_deck")` returns structured slide JSON; server renders to reveal.js HTML via Jinja2 template
- [ ] **Custom theme per workspace:** CSS theme variables mapping brand colors, fonts, and logo to reveal.js theme — applied server-side at render time
- [ ] **Image & logo zones:** Designated slide sections for logo placement, product screenshots, and background images with URL or upload support
- [ ] **Speaker notes:** LLM generates presenter notes per slide grounded in the full messaging context
- [ ] **PDF export:** reveal.js `?print-pdf` mode → `window.print()` → browser PDF engine; output is significantly higher quality than jsPDF
- [ ] **`build_presentation` MCP tool:** Returns a link to a live reveal.js presentation for a given message house and presentation type

### Penpot — High-Fidelity Design Export
Penpot is a self-hosted Figma alternative with a full design API. MsgStack already has the Penpot MCP server connected. For artifacts where pixel-perfect design quality matters most, MsgStack can programmatically create a fully designed document in Penpot — complete with brand fonts, vector assets, image frames, and design tokens — and hand the user an edit link.

- [ ] **Penpot project per workspace:** Auto-create a MsgStack workspace in Penpot mapped to each MsgStack workspace; store the Penpot project ID on the workspace record
- [ ] **Design token sync:** Map MsgStack brand color tokens and font settings to Penpot design tokens; push on workspace update
- [ ] **Programmatic artifact creation:** Use the Penpot API to create a fully designed page for each artifact type — frames, text layers, image frames, brand colors, logo placeholder
- [ ] **`export_to_penpot` MCP tool:** Creates the artifact in Penpot and returns an edit link; user lands in Penpot to do final polish and export
- [ ] **Penpot → MsgStack round-trip (stretch):** Pull approved design decisions (updated logo, adjusted color) back from Penpot into MsgStack brand tokens

### Shared Infrastructure
- [ ] **`ArtifactRenderer` abstraction:** Common interface (`render_html`, `render_fabric`, `render_reveal`, `render_penpot`) so new rendering targets can be added without touching `generate_artifact`
- [ ] **Artifact type → renderer routing:** Skill metadata includes a `renderer` field (`html`, `fabric`, `reveal`, `penpot`) — `generate_artifact` routes accordingly
- [ ] **Brand asset store:** Per-workspace storage for logos, icons, and brand images referenced by all renderers; API endpoints for upload and retrieval

---

## v0.9 — Document Source Integrations (Google Drive + OneDrive/SharePoint)

**Goal:** Connect MsgStack directly to where marketing documents already live — eliminating the manual upload step and keeping frameworks automatically in sync as source documents evolve.

### Google Drive Integration
- [ ] **OAuth2 Connector:** Authenticate with a Google account and authorize Drive access via OAuth2 PKCE flow
- [ ] **Drive Picker UI:** Embed the Google Drive file picker in the Upload section for manual selection from Drive without leaving MsgStack
- [ ] **Folder Watch:** Monitor a designated Drive folder for new or modified files (PDF, DOCX, Google Docs, Slides) — auto-trigger the extraction + structuring pipeline when a file is added or updated
- [ ] **Google Docs native export:** Export Google Docs directly via the Drive export API (preserving heading structure and tables) rather than converting to PDF — higher extraction fidelity
- [ ] **Sync status per framework:** "Source in Drive" badge with last synced timestamp; "outdated" warning badge when the Drive file is newer than the structured framework
- [ ] **Conflict diff UI:** When a monitored file is updated, show a structured diff of changed sections before auto-accepting and re-ingesting
- [ ] **Push back to Drive (optional):** Export the finalized Message House as a formatted Google Doc and save it back to a specified Drive folder

### OneDrive & SharePoint Integration
- [ ] **Microsoft MSAL Auth:** OAuth2 PKCE flow for OneDrive personal accounts and SharePoint Online via Microsoft Graph API
- [ ] **OneDrive Folder Watch:** Monitor a OneDrive folder for new/updated files — same auto-ingest trigger as Google Drive
- [ ] **SharePoint Document Library Watch:** Monitor a SharePoint site's document library; support multiple sites per workspace
- [ ] **Microsoft Graph Webhooks:** Real-time change notifications via Microsoft Graph webhook subscriptions (avoids polling for SharePoint Online)
- [ ] **Word Online Documents:** Native extraction via Microsoft Graph `content` endpoint — pull `.docx` bytes directly without manual download
- [ ] **Sync Scheduler Fallback:** Configurable polling interval for organizations that can't use webhooks (on-prem SharePoint, firewall restrictions)
- [ ] **SharePoint Site Browser:** UI panel to browse SharePoint sites and document libraries within MsgStack

### Source Sync Infrastructure
- [ ] **SourceConnector Abstraction:** Pluggable connector interface (`connect()`, `watch()`, `fetch()`, `push()`) so Notion, Confluence, and Box can be added in future milestones without touching core pipeline code
- [ ] **Sync Job Queue:** SQLite-backed background job queue for processing ingest triggers asynchronously (no Celery dependency for single-process deployments)
- [ ] **Sync Dashboard Widget:** Dashboard panel showing all connected sources, per-framework last sync status, and failed/pending sync jobs with retry controls
- [ ] **Per-Framework Source Record:** Store `source_type` (`google_drive`, `onedrive`, `sharepoint`, `upload`, `manual`), `source_id` (file/folder ID), and `source_last_modified` on each framework
- [ ] **Manual Re-Sync Button:** Per-framework "Sync from source" button to force an immediate refresh from the connected source

---

## v1.0 — Advanced Graph Operations & Visualization

**Goal:** Enable graph-powered insights and cross-document intelligence.

### Graph-Powered Queries
- [ ] **Persona Coverage Analysis:** Which messages address which personas? Identify coverage gaps.
- [ ] **Channel Reachability:** Which channels can a message reach through APPLIES_TO relationships?
- [ ] **Cross-Framework Comparison:** Compare messaging relationships across multiple houses

### Cross-Document Intelligence
- [ ] **GroundingCollection:** Bundle multiple documents (brand guide + message house + persona library) into a named collection. MCP tools target the entire collection for search and artifact generation.
- [ ] **INFORMS Edge:** `(GroundingDocument) -[:INFORMS]-> (GroundingDocument)` cross-document relationship. Graph traversal follows `INFORMS` edges to surface the source-of-truth document behind a message.
- [ ] **Path Finder UI:** Visualize relationship paths between entities (e.g., "how does this message reach this persona?")

### Graph Maintenance
- [ ] **Sync Pipeline:** Keep graph in sync with SQLite/PostgreSQL changes on every write
- [ ] **Backup & Restore:** Include graph state in the snapshot system
- [ ] **Neo4j Migration Path:** Adapter layer enabling drop-in replacement of in-process NetworkX graph with Neo4j for scale

---

## v1.1 — Platform & Ecosystem

**Goal:** MsgStack as a platform other tools and workflows integrate with.

### Additional Integrations
- [ ] **Notion connector** — Sync frameworks to/from Notion pages
- [ ] **Slack app** — Query messaging and generate artifacts via Slack command
- [ ] **HubSpot / Salesforce** — Push approved messaging to CRM as snippet library
- [ ] **Confluence connector** — Watch a Confluence space for source documents

### Advanced Search & Governance
- [ ] **Cross-framework search** — "What do all our product teams say about security?"
- [ ] **Gap analysis** — "Which frameworks lack proof points for the CISO persona?"
- [ ] **Audit Trail** — Comprehensive changelog of all framework modifications

### Auth & Identity
- [ ] **OIDC / OAuth login** — Replace manual API key distribution with SSO (Google, Okta, Azure AD)
- [ ] **Workspace invites** — Email-based invite flow with role assignment

---

## Backlog (Unscheduled)

- Multi-LLM support (Anthropic Claude, Gemini, local Ollama)
- Custom embedding models
- Import from PPTX
- CLI tool (`msgstack search "..."`)
- VS Code extension for inline messaging suggestions
- Inline rich-text editor (TinyMCE/Quill) for polishing AI drafts

---

## What We're Not Building

- A full CMS or social media scheduling tool
- A CRM replacement
- Real-time chat/collaboration

MsgStack is messaging infrastructure — the data layer and search/generation API.
