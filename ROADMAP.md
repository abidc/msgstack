# MsgStack — Roadmap

**Last Updated:** May 2026  
**License:** Apache 2.0 — open source, self-hostable  
**Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md)

This roadmap reflects current state and planned direction. Items are grouped by milestone, not calendar quarter — sequencing depends on community feedback and priority shifts. Items marked `[OSS]` are well-suited for community contribution.

---

## v0.6.1 — OSS Launch Polish

**Goal:** Make the repository welcoming and navigable for first-time contributors and self-hosters.

- [x] MIT → Apache 2.0 license
- [x] Rewritten README — community-focused, clear quick start
- [x] `CONTRIBUTING.md` with dev setup guide
- [x] GitHub issue templates (bug report, feature request)
- [x] PR template
- [x] Removed internal dev-only files from repo root
- [x] `docs/` directory for architecture and brand docs
- [x] `.gitignore` cleaned up

---

## Current State — v0.8.2 (May 2026)

**Shipped (Milestones v0.1 - v0.6):**
- ✅ FastMCP server with 15 grounding + artifact tools over streamable-HTTP
- ✅ FastAPI admin UI with full Frameworks/Skills/Workspaces management
- ✅ **Advanced Upload Pipeline:** PDF/DOCX/TXT → Multi-chunk structuring → Vector index
- ✅ **Preview & Confirm:** Extract and review structured messaging before committing to DB
- ✅ **LLM Persona Parsing:** Robust JSON extraction replacing regex state machines
- ✅ **Hybrid Search:** Vector + keyword overlap reranking with `min_confidence` control
- ✅ **Versioning:** Snapshot system for history, diffing, and restoration
- ✅ **Artifact Pro:** Generate 12+ artifact types with DOCX/PDF export and visual previews
- ✅ **Artifact History:** Persistent storage and retrieval of all generated content
- ✅ **Multi-Tenancy:** Workspace-scoped frameworks, API keys, and vector namespaces
- ✅ **Production Auth:** Scoped API key authentication (`read`/`write`/`admin`)
- ✅ **Operations:** Structured logging, rate limiting, and workspace token budgets
- ✅ **Jinja2 UI Architecture:** Admin UI migrated to `base.html` + `dashboard.html`
- ✅ **Dark Artifact Visual Page:** `/artifact/one_pager/{id}` renders with dark theme, color-coded sections
- ✅ **Tabbed House Detail:** Overview (editable), Messages (color-coded, drag-to-reorder), Personas tabs
- ✅ **Skill Context Inputs:** Skills requiring context surface input fields before generation
- ✅ **Multi-Content-Type:** `document_type` discriminator with color-coded badges
- ✅ **Knowledge Graph Engine:** NetworkX DiGraph — deterministic retrieval via typed entity relationships
- ✅ **Graph Explorer UI:** Interactive Cytoscape.js canvas with node filtering and detail panel
- ✅ **Extended Graph Entities:** MessagingPillar, PainPoint, BuyingTrigger, Objection as first-class graph nodes
- ✅ **`get_graph_connections` MCP Tool:** Deterministic graph traversal bypassing vector approximation
- ✅ **Full-Context Grounding:** ALL key messages + ALL persona attributes in every artifact prompt
- ✅ **Grounding Guardrails:** `list_message_houses` MANDATORY_NEXT_ACTION field directing agents to call tools
- ✅ **Google Drive Sync:** Background sync loop with DOCX/PDF native format support
- ✅ **Fabric.js Canvas Shell:** `/canvas` route + basic `one_pager_visual` skill + design JSON → canvas rendering (primitive — foundation only)
- ✅ **Canvas Routing:** `one_pager` skill now routes to `/canvas?artifact_id=...` instead of static HTML
- ✅ **Turbovec Local Vector DB** (`v0.8.1`): replaced Pinecone with in-process quantized vector search — zero external dependencies, <0.1ms query latency
- ✅ **Automatic Markdown Translation Layer** (`v0.8.2`): high-fidelity DOCX/PDF proxy files saved to `data/sources/{id}.md` and indexed under `source_markdown` section type for full-content RAG including tables and complex formatting

**Known gaps and active issues:**
- Visual artifact output is primitive — canvas renders basic zones without professional layout, brand system, or template design
- `one_pager` skill prompt produces truncated/incomplete section content in some cases
- Design JSON schema is too simple (hero/positioning/messages only) — no brand tokens, column grid, or icon zones
- No workspace-level brand settings (colors, fonts, logo) — all artifacts use default styling
- No defined per-artifact-type templates (datasheet, battlecard, social card each need their own design DNA)
- Canvas app has no interactive editing beyond basic zone display
- OIDC/OAuth login not yet implemented (API key auth only)
- Channel still a code enum (DB entity promotion not yet done)
- Multimodal/vision model fallback not yet implemented

---

## v0.7 — Knowledge Graph Completion

**Goal:** Complete the remaining graph and governance items before moving to the visual artifact engine.

### Channel as a First-Class Entity
- [x] **ChannelModel DB table:** Promote `Channel` from a code enum to a SQLAlchemy table with full CRUD endpoints
- [x] **Seed defaults:** `all`, `email`, `linkedin`, `twitter`, `paid_ads`, `landing_page`, `sales_deck`
- [x] **User-defined channels:** Create custom channels via UI without code changes
- [x] **Graph node upgrade:** Channel nodes backed by DB rows with full metadata

### Graph Governance
- [x] **Approval Workflow:** Mark Key Messages as `Draft` or `Approved`; grounding prioritizes `Approved`
- [x] **Locking:** Prevent editing of "Core Messaging" once approved
- [x] **Artifact Status:** Lifecycle tracking: `Draft` → `Internal Review` → `Approved`
- [x] **Staleness Alerts:** "Last Reviewed" timestamp per framework; flag frameworks older than 90 days
- [x] **Review Trail:** Log of who reviewed/approved messaging updates and when

### Feedback Loop
- [x] **Content Ratings:** Rate generated artifacts (1-5 stars) or Good/Bad tags
- [x] **Self-Correction:** Boost relevance for messaging chunks used in high-rated artifacts
- [x] **Usage Heatmap:** See which parts of the message house are used most vs ignored

---

## v0.8 — Visual Artifact Engine

**Goal:** Produce professional, brand-accurate visual artifacts from messaging house data. This is a full design engineering effort — not just a rendering fix. Three interdependent work streams must come together: a design system that defines what artifacts look like, an LLM prompt layer that generates rich structured design specs from messaging content, and a canvas renderer capable of faithfully executing those specs.

The current canvas shell is a starting point only. This milestone rebuilds it from the ground up with production-quality output as the success criterion. A generated HR datasheet should be indistinguishable in quality from one a designer produced manually in Figma.

---

### Stream 1 — Design System Foundation

Everything visual artifacts need before any template or renderer work begins.

#### 1a. Design JSON Schema (v2)
The current schema (`{zones: [{type, text}]}`) is too primitive to express a professional layout. Replace it with a structured spec that captures every visual decision a renderer needs.

- [ ] **Page spec:** `{width, height, orientation, margin}` — support Letter (8.5×11), A4, and 16:9 slide presets
- [ ] **Layout grid:** Column count, gutter width, row rhythm — renderers snap zones to the grid
- [ ] **Zone types (expanded):**
  - `header` — brand bar with logo zone + product name + optional tagline
  - `hero` — large headline text with optional background color or image
  - `positioning_block` — 2-3 sentence body paragraph with optional lead-in label
  - `pillar_grid` — N-column grid of differentiator cards, each with icon zone + headline + body
  - `message_list` — labeled list of key messages, optionally grouped by section type
  - `persona_strip` — horizontal row of persona cards, each with name + role + 2 pain points
  - `proof_block` — stat callout or pull quote with large number + label
  - `cta_footer` — call to action + URL + contact info + logo
- [ ] **Zone properties:** `row`, `col`, `colspan`, `text_content`, `text_style` (heading/body/caption), `background`, `icon_type`, `image_zone`, `list_items[]`, `emphasis` (primary/secondary/muted)
- [ ] **Brand token references in zones:** `{{brand.primary}}`, `{{brand.font_heading}}` — resolved at render time from workspace brand settings
- [ ] **Schema version field:** enables forward compatibility when schema evolves

#### 1b. Workspace Brand Settings
- [ ] **Brand token model:** `primary_color`, `secondary_color`, `accent_color`, `background_color`, `text_color`, `font_heading`, `font_body` stored per workspace
- [ ] **Logo storage:** Per-workspace logo upload (PNG/SVG); stored in `data/brand/{workspace_id}/`; API endpoints for upload and retrieval
- [ ] **Brand settings UI:** Settings page section — color pickers, font selectors, logo upload with preview
- [ ] **Token resolution at render time:** Canvas renderer and reveal.js theme renderer both resolve `{{brand.*}}` tokens from workspace settings before drawing
- [ ] **Default brand palette:** Professional neutral default (slate + indigo accent) applied when no brand settings exist — better than no styling at all

#### 1c. Artifact Template Registry
- [ ] **Template definition format:** JSON files in `data/templates/` defining the zone layout, ordering, and styling defaults for each artifact type
- [ ] **Template fields:** `artifact_type`, `page_spec`, `zones[]` (with type + position + default styling), `brand_zones[]` (which zones receive brand token replacement)
- [ ] **Built-in templates (see Stream 2 for design specs):** `datasheet`, `battlecard`, `social_card`, `event_brief`, `executive_summary`, `sales_deck_slide`
- [ ] **Template selection:** `generate_artifact` looks up the template for the skill's `artifact_type` before calling the LLM; template structure is injected into the LLM prompt
- [ ] **Template UI:** Admin UI view for browsing and previewing available templates

---

### Stream 2 — Default Template Designs

This stream defines what each artifact type should actually look like — the design decisions a skilled designer would make. These are the reference specifications that both the LLM prompts and the canvas renderer implement.

#### 2a. Datasheet / One-Pager Template

The primary artifact type. Portrait orientation, letter size. B2B sales motion. High information density with clear visual hierarchy.

**Layout (top to bottom):**
1. **Brand Header bar** (full-width, brand primary color): logo left + product/service name center + optional "Powered by [brand]" badge right
2. **Hero section** (full-width, brand secondary or neutral): Tagline in large heading font, 1-line positioning statement below in body size
3. **3-Column Differentiator Grid**: Each column has an icon zone (placeholder or icon font), bold differentiator headline (max 6 words), and 1-2 sentence supporting body. This is the most visually prominent section.
4. **Key Messages section**: 2-column grid of message cards. Each card has a section-type label (Headline / Benefit / Use Case / Proof Point), the message text, and an optional channel tag. Grouped by priority — top 6 messages shown.
5. **Audience section**: Horizontal strip with persona cards. Each card: persona name + role title + 2 bullet pain points. Up to 3 personas. If more exist, truncate to fit.
6. **Proof / Social Proof strip** (optional): 3 stat blocks in a row — large number + label (e.g., "40% reduction in HR case volume"). Omit if no stats in the messaging house.
7. **CTA Footer** (full-width, brand primary): One-line CTA statement + URL + logo small

**Typography:** Heading font for headlines, body font for supporting copy. Font sizes: H1 36pt, H2 22pt, H3 16pt, body 11pt, caption 9pt.

**Color use:** Brand primary for header/footer/accent. Brand secondary or light neutral for differentiator grid background. White or off-white for body sections. Section labels in brand accent color.

- [x] **Design spec JSON for datasheet template** — codify the above as a `data/templates/datasheet.json` template definition
- [x] **LLM mapping logic** — define which messaging house fields map to which zones: `tagline → hero headline`, `positioning → hero body`, `differentiation bullets → pillar_grid`, `top 6 key messages by priority → message_list`, `personas → persona_strip`, `proof points → proof_block`

#### 2b. Battlecard Template

Landscape orientation. Competitive sales aid. Two-column structure: "Us" vs "Them" or "Us" vs "Objection + Response."

**Layout:**
1. **Header**: Product name left, competitor name right, battlecard label center
2. **Positioning row** (full-width): Our one-line positioning
3. **2-Column grid** — left column: key differentiators and strengths; right column: common objections with verbatim responses from messaging house
4. **Bottom strip**: Top 3 proof points or win stats; key personas targeted

- [x] **Design spec JSON for battlecard template**
- [x] **LLM mapping logic for battlecard** — requires `competitor` context input; uses `differentiation`, `objections`, `proof_points` sections

#### 2c. Social Card Template

Square (1:1) or Story (9:16). Single focused message for LinkedIn, Twitter/X, or Instagram. Minimal text, bold visual hierarchy.

**Layout:**
1. Full-bleed background (brand gradient or solid)
2. Single headline (the most relevant key message, max 12 words) — large, centered
3. 1-line supporting context — small, centered below headline
4. Logo bottom right + optional URL

- [x] **Design spec JSON for social card template**
- [x] **LLM mapping logic** — select highest-priority message for the target channel; apply channel-specific tone

#### 2d. Executive Summary Template

Portrait, Letter, minimal and clean. For C-suite briefings and board materials. Minimal graphics, maximum copy clarity.

**Layout:**
1. Title + subtitle header
2. Full-width positioning paragraph (slightly larger body text)
3. 3 key strategic pillars — numbered, bold headline + 3-4 sentences each
4. Audience and use case table (2-column: Persona | Primary Value Delivered)
5. Clean footer

- [x] **Design spec JSON for executive summary template**

---

### Stream 3 — LLM Prompt Engineering for Visual Spec

The current `one_pager_visual` prompt asks the LLM to "return a JSON object" with minimal guidance. The output is unreliable and the content is sparse. This stream rewrites the generation path so the LLM produces rich, accurate, brand-ready design specs.

#### 3a. Skill Prompt Rewrites

- [x] **`one_pager_visual` prompt rewrite:** Inject the template zone structure into the prompt so the LLM maps messaging house content to specific zones by name. Include field-level instructions ("tagline → hero.text_content; keep under 10 words"), output format examples with realistic content, and a grounding reminder ("use only content from the messaging house — no invented statistics").
- [x] **New `datasheet` skill:** Separate from `one_pager_visual`. Uses the datasheet template. Prompt instructs the LLM to populate each zone from the correct messaging source field. Section-type priority rules baked in (Headline messages → pillar headlines; Benefit messages → pillar bodies; Proof Point messages → proof_block stats).
- [x] **`battlecard_visual` prompt:** Populates battlecard template zones. Requires competitor name. Pulls objections + responses from graph for verbatim accuracy.

#### 3b. Content-to-Zone Mapping Engine

The LLM shouldn't have to figure out which message goes in which zone on its own — the context block should do this work.

- [x] **`_build_visual_context()` function:** Extend `generator.py` with a visual-specific context builder that pre-assigns messaging house content to template zones before the LLM call. The LLM's job becomes copy-editing and tone-polishing, not data organization.
- [x] **Priority-based selection:** When a zone has a capacity constraint (e.g., pillar_grid shows 3 items, proof_block shows 3 stats), `_build_visual_context()` pre-selects the highest-priority candidates before passing them to the LLM.
- [x] **Persona truncation rules:** Persona strip shows max 3 personas. Selection order: primary persona first, then by completeness score (most complete pain points + triggers shown first).

#### 3c. Design Spec Validation

The LLM output must be validated before it reaches the renderer. Malformed specs cause silent rendering failures that are hard to debug.

- [x] **Pydantic schema for design spec:** `DesignSpec`, `Zone`, `ZoneContent` models — validate LLM output before saving; auto-fill missing optional fields with template defaults
- [x] **Fallback fill:** If LLM omits a required zone, the validator injects the template default content (pulled from the messaging house directly)
- [x] **Token budget guardrail:** Design spec generation prompt has a tighter token budget than prose generation — zone content should be concise; validator truncates oversized text blocks to zone capacity limits

---

### Stream 4 — Canvas Renderer (Fabric.js)

The current canvas app renders basic zones. This stream rebuilds the renderer to faithfully execute the v2 design spec with production-quality output.

#### 4a. Zone Renderer Implementation

- [x] **Zone type renderers:** Implement a Fabric.js renderer function for each zone type defined in Stream 1a — `header`, `hero`, `positioning_block`, `pillar_grid`, `message_list`, `persona_strip`, `proof_block`, `cta_footer`
- [x] **Grid layout engine:** Parse the zone's `row`/`col`/`colspan` properties to place zones on the page grid. Zones that overflow their column collapse gracefully rather than overlapping.
- [x] **Typography rendering:** Apply `text_style` values to Fabric.js text objects — heading/body/caption each map to a configured font size, weight, and line height
- [x] **Brand token resolution:** Before rendering, resolve all `{{brand.*}}` placeholders from workspace brand settings fetched via `/api/workspaces/{id}/brand`
- [x] **Image zones:** Render logo and image placeholder zones as styled rectangles with centered label text ("Your Logo Here"); support `fabric.Image.fromURL()` for live URL replacement

#### 4b. Interactive Editing

- [x] **Text click-to-edit:** Double-click any text zone to enter edit mode using Fabric.js's native `IText` — changes persist to the artifact's `design_spec` via `PATCH /api/artifacts/{id}/design_spec`
- [x] **Logo drag-and-drop:** Click logo zone → file picker → `fabric.Image.fromURL(base64)` replaces placeholder; save button persists to artifact
- [x] **Color override:** Zone background color picker; updates `background` in the zone spec
- [x] **Section reorder:** Drag zones vertically to reorder (updates `row` values in spec, triggers re-render)
- [x] **Reset to AI version:** One-click restore to the LLM-generated spec before edits

#### 4c. Export Pipeline

- [x] **PNG export:** `canvas.toDataURL('image/png', 2.0)` at 2× resolution for retina quality; download triggered client-side
- [x] **PDF export (jsPDF):** Serialize each canvas object to jsPDF; preserve vector text where possible; fallback to image embed for complex zones
- [x] **SVG export:** `canvas.toSVG()` for design hand-off to Figma or Illustrator
- [x] **Print-ready mode:** 300 DPI equivalent scaling before PNG export; web fonts loaded and resolved before capture

---

### Stream 5 — reveal.js (Presentations)

- [x] **Slide skill templates:** `sales_deck`, `event_presentation`, `executive_readout` — each with structured slide schemas
- [x] **LLM slide generation:** `generate_artifact(skill_id="sales_deck")` returns structured slide JSON; Jinja2 renders to reveal.js HTML
- [x] **Custom workspace theme:** CSS variables mapping brand colors, fonts, logo to reveal.js theme applied server-side
- [x] **Image & logo zones:** Designated slide sections with placeholder support
- [x] **Speaker notes:** Generated per slide from full grounding context
- [x] **PDF export:** reveal.js `?print-pdf` + browser print engine (higher quality than jsPDF)
- [x] **`build_presentation` MCP tool:** Returns live reveal.js presentation URL

---

### Stream 6 — Penpot (Highest-Fidelity Design Export)

- [ ] **Penpot project per workspace:** Auto-create MsgStack workspace in Penpot; store Penpot project ID on workspace record
- [ ] **Design token sync:** Map MsgStack brand tokens to Penpot design tokens; push on workspace update
- [ ] **Programmatic artifact creation:** Use Penpot API to create fully designed pages — frames, text layers, image frames, brand colors
- [ ] **`export_to_penpot` MCP tool:** Creates artifact in Penpot, returns edit link
- [ ] **Penpot → MsgStack round-trip (stretch):** Pull approved design decisions back from Penpot into MsgStack brand tokens

---

### Stream 7 — Premium Canvas Templates & Engine Deep Dive (v0.8 Core Phase 2)

- [ ] **Canvas Engine Refactor:** Fix core rendering issues in the Fabric.js editor — resolve grid overlapping, ensure dynamic text resizing scales cleanly without breaking the grid, apply consistent padding and margin standards.
- [ ] **Data Mapping Fixes:** Resolve `{placeholder}` leaks (e.g. `{proof_point}`, `{house_name}`) failing to properly interpolate grounded data before reaching the canvas render engine.
- [ ] **High-Impact Templates (5-10):** Design and implement highly polished, premium aesthetic JSON template schemas (e.g., Executive 1-Pager, Product Tear-Sheet, Capability Brief, ROI One-Pager, Persona Profile, Feature Release, Case Study).
- [ ] **Premium Typography & Styling:** Implement modern, premium typography sets, drop shadows, border radiuses, and glassmorphism token support within the Canvas engine.

---

### Shared Infrastructure (v0.8)
- [ ] **`ArtifactRenderer` abstraction:** Common interface (`render_html`, `render_fabric`, `render_reveal`, `render_penpot`) — new rendering targets added without touching `generate_artifact`
- [ ] **Renderer routing via skill metadata:** `renderer` field on each skill JSON routes `generate_artifact` to the correct path
- [ ] **Brand asset store:** Per-workspace storage for logos, icons, and brand images; API endpoints for upload and retrieval; referenced by all renderers

---

## v0.9 — Governance & Alignment Engine

**Goal:** Make MsgStack the messaging governance layer, not just a generation tool. This milestone introduces the features that give marketing ops a reason to open MsgStack every week — not just when they need a new artifact.

### Alignment Scoring
The most novel capability in the roadmap. Evaluates any piece of content against the structured message house and returns a per-section alignment report. Possible only because the message house is machine-readable — no other tool can do this.

- [ ] **`score_alignment` API endpoint:** Accepts arbitrary text + house_id; returns per-section scores (0–100) plus specific gaps and contradictions against approved messaging
- [ ] **`score_alignment` MCP tool:** AI assistants can score a draft before submitting it — "check this LinkedIn post against the CHRO persona messaging before I publish"
- [ ] **Alignment report UI:** Paste content into the admin UI → receive color-coded alignment breakdown with specific suggestions ("Missing: proof point about efficiency. Contradicts: positioning on AI autonomy.")
- [ ] **Batch scoring:** Connect a HubSpot content library or Google Drive folder → score all assets against the active house → report sorted by alignment score
- [ ] **Drift report:** Weekly summary of all generated artifacts that have diverged from the message house since it was last updated
- [ ] **Alignment score on artifact history:** Every saved artifact record shows its alignment score at time of generation; re-scored automatically when the house is updated

### Message Approval Workflow
- [ ] **Message status field:** `Draft` | `In Review` | `Approved` | `Outdated` | `Locked` on every key message, persona, and house field
- [ ] **Approval-gated generation:** `generate_artifact` and grounding search skip non-`Approved` messages by default; optional `include_drafts` override for authoring sessions
- [ ] **Review request flow:** Author marks message as "Ready for Review" → reviewer receives notification → approves or comments → status updates → vector index refreshed
- [ ] **Drift detection:** When a message is updated, all artifact history records that used it are flagged as potentially outdated
- [ ] **Locked messages:** "Core Messaging" locked status prevents any edits without admin override; graph retrieval always returns locked messages verbatim

### Self-Service Field Portal
- [ ] **Portal URL per workspace:** Shareable link (no MsgStack account required) scoped to one or more approved message houses
- [ ] **Simplified generation UI:** Persona selector → artifact type selector → optional context inputs → generate → download/share
- [ ] **Generation-only access:** Portal users cannot view or edit the message house; they only see approved messages in the artifact output
- [ ] **Agency submission mode:** Generated artifacts go to a "Pending Approval" queue rather than being immediately downloadable; marketing manager approves before agency can use
- [ ] **Portal analytics:** Log all field portal generation activity — who generated what, when, with which inputs — for audit and usage insight

---

## v1.0 — Competitive Intelligence

**Goal:** Make battlecards and competitive content accurate against what competitors are actually saying, not just what you wish they were saying.

- [ ] **Competitor document import:** Upload competitor website pages, datasheets, or sales decks → structuring pipeline extracts their message structure into a `competitive_brief` house
- [ ] **Competitive gap analysis:** Compare your message house to a competitor's extracted house — where are you weak? Where are you differentiated? Surface specific messages that counter their actual claims.
- [ ] **Battlecard auto-sharpen:** When generating a battlecard, automatically load the competitor's extracted house and ensure each response directly counters their stated positioning
- [ ] **Competitor change detection (stretch):** Periodic re-fetch of monitored competitor URLs; alert when messaging has materially changed and existing battlecards need refreshing
- [ ] **Competitive landscape view:** Admin UI panel showing all imported competitor houses with last-updated timestamp and key positioning differences

---

## v1.1 — Publishing Integrations

**Goal:** Close the gap between "generated" and "published." Content should move from MsgStack to the channel it's destined for without copy-paste, which is where grounding breaks.

- [ ] **HubSpot integration:** Push email templates directly into HubSpot email drafts; push social posts to HubSpot social publish queue; pull existing HubSpot assets for alignment scoring
- [ ] **LinkedIn integration:** Publish social card artifacts to LinkedIn company page or personal profile via LinkedIn API; pull recent posts for alignment scoring
- [ ] **Salesforce integration:** Push approved key messages and battlecard content into Salesforce CRM as content snippets accessible to reps in opportunity records
- [ ] **Google Docs export:** Export any artifact as a formatted Google Doc into a designated Drive folder — closes the agency collaboration loop without email
- [ ] **Slack app:** `/msgstack generate one-pager [house name]` slash command returns grounded content in Slack; no admin UI required for field teams
- [ ] **Webhook outbound:** Generic webhook on artifact generation — send any generated artifact to any external system via POST

---

## v1.2 — Activation & Built-In AI Interface

**Goal:** A VP of Marketing can evaluate and adopt MsgStack without involving IT or a developer. First artifact in under 5 minutes from landing on the product.

### Onboarding & Activation
- [ ] **Hosted SaaS mode:** Cloud-hosted instance with managed database, vector index, and server — no infrastructure decisions required
- [ ] **Onboarding wizard:** Upload document → review extracted message house → generate first artifact → share link — no configuration steps
- [ ] **Industry starter templates:** Pre-built message house skeletons for B2B SaaS, Professional Services, Enterprise Software, Financial Services — shows users what a complete house looks like before they build one
- [ ] **Completeness coaching:** Admin UI actively prompts to fill gaps with specific value-add language ("Your house is missing proof points — battlecard generation requires at least 2")
- [ ] **Sample house:** "Try MsgStack with an example" — loads a pre-built demo house so users can explore generation before committing to their own content

### Built-In AI Chat Interface
- [ ] **Chat panel in admin UI:** Embedded chat interface — model pre-instructed with `system_instructions`, active house pre-loaded, grounding automatic; no MCP client required
- [ ] **Conversation starters:** Pre-configured prompt links for common tasks — "Generate CHRO LinkedIn post," "Write a battlecard vs Workday," "Summarize this framework for a new hire"
- [ ] **Shareable session links:** Marketing manager creates a pre-configured session link and sends it to a colleague or agency — they click it and are dropped into a ready-to-use chat with the right house and persona context already set
- [ ] **Multi-LLM support:** Bring-your-own API key for OpenAI, Anthropic Claude, Azure OpenAI, or Google Gemini — workspace-level model setting with fallback

### Content Analytics
- [ ] **Message usage heatmap:** Which key messages appear most in generated artifacts — surface dead messages that need to be revised or removed
- [ ] **Artifact engagement:** Views, downloads, and shares of hosted artifact links
- [ ] **Generation → export rate:** Percentage of generated artifacts that were downloaded (proxy for quality)
- [ ] **Per-persona coverage:** Are all personas in the house served by the key message set? Flag gaps.

---

## v1.3 — Document Source Integrations

**Goal:** Connect MsgStack directly to where marketing documents already live — eliminating the manual upload step and keeping frameworks automatically in sync as source documents evolve.

### Google Drive Integration
- ✅ OAuth2 Connector — authenticate and authorize Drive access
- ✅ Background sync loop — monitor folder for changed files, auto-ingest
- ✅ DOCX native format support — binary DOCX correctly detected and extracted
- [ ] **Drive Picker UI:** Embed Google Drive file picker in the Upload section
- [ ] **Sync status UI:** "Source in Drive" badge; "outdated" warning when Drive file is newer
- [ ] **Conflict diff UI:** Show structured diff of changed sections before re-ingesting
- [ ] **Push back to Drive (optional):** Export finalized Message House as a formatted Google Doc

### OneDrive & SharePoint Integration
- [ ] **Microsoft MSAL Auth:** OAuth2 PKCE flow for OneDrive and SharePoint Online via Microsoft Graph API
- [ ] **OneDrive Folder Watch:** Same auto-ingest trigger as Google Drive
- [ ] **SharePoint Document Library Watch:** Monitor a SharePoint site's document library
- [ ] **Microsoft Graph Webhooks:** Real-time change notifications (avoids polling)
- [ ] **Word Online Documents:** Native extraction via Microsoft Graph `content` endpoint
- [ ] **Sync Scheduler Fallback:** Configurable polling interval for organizations that can't use webhooks
- [ ] **SharePoint Site Browser:** UI panel to browse sites and document libraries within MsgStack

### Source Sync Infrastructure
- [ ] **SourceConnector Abstraction:** Pluggable connector interface (`connect()`, `watch()`, `fetch()`, `push()`) for Notion, Confluence, Box in future milestones
- [ ] **Sync Dashboard Widget:** Dashboard panel showing all connected sources, per-framework sync status, failed/pending jobs with retry controls
- [ ] **Manual Re-Sync Button:** Per-framework "Sync from source" button to force an immediate refresh

---

## v1.4 — Advanced Graph Operations & Visualization

### Graph-Powered Queries
- [ ] **Persona Coverage Analysis:** Which messages address which personas? Identify coverage gaps.
- [ ] **Channel Reachability:** Which channels can a message reach through APPLIES_TO relationships?
- [ ] **Cross-Framework Comparison:** Compare messaging relationships across multiple houses

### Cross-Document Intelligence
- [ ] **GroundingCollection:** Bundle multiple documents (brand guide + message house + persona library) into a named collection
- [ ] **INFORMS Edge:** Cross-document relationship — graph traversal surfaces the source-of-truth document behind a message
- [ ] **Path Finder UI:** Visualize relationship paths between entities

### Graph Maintenance
- [ ] **Sync Pipeline:** Keep graph in sync with SQLite/PostgreSQL changes on every write
- [ ] **Backup & Restore:** Include graph state in snapshot system
- [ ] **Neo4j Migration Path:** Adapter layer enabling drop-in replacement of NetworkX with Neo4j for scale

---

## v1.5 — Platform & Ecosystem

### Additional Integrations
- [ ] **Notion connector** — Sync frameworks to/from Notion pages
- [ ] **Slack app** — Query messaging and generate artifacts via Slack command
- [ ] **HubSpot / Salesforce** — Push approved messaging to CRM as snippet library
- [ ] **Confluence connector** — Watch a Confluence space for source documents

### Auth & Identity
- [ ] **OIDC / OAuth login** — Replace manual API key distribution with SSO (Google, Okta, Azure AD)
- [ ] **Workspace invites** — Email-based invite flow with role assignment

### Advanced Search & Governance
- [ ] **Cross-framework search** — "What do all our product teams say about security?"
- [ ] **Gap analysis** — "Which frameworks lack proof points for the CISO persona?"
- [ ] **Audit Trail** — Comprehensive changelog of all framework modifications

---

## Backlog (Unscheduled)

- Multi-LLM support (Anthropic Claude, Gemini, local Ollama)
- Custom embedding models
- Import from PPTX
- CLI tool (`msgstack search "..."`)
- VS Code extension for inline messaging suggestions
- Inline rich-text editor for polishing AI drafts
- Print-First Documents via Paged.js (typeset PDFs with real margins and bleed)

---

## What We're Not Building

- A full CMS or content calendar (we generate and publish; we don't manage the editorial schedule)
- A social media scheduling platform (publishing integrations push to existing schedulers, not replace them)
- A CRM (Salesforce/HubSpot integrations push content into CRMs; we don't replace them)
- A design tool (Fabric.js canvas and Penpot export complement design tools; they don't replace Figma)
- A localization platform (localization is a quality-of-life feature, not the core problem)

MsgStack is **messaging governance infrastructure** — the structured, machine-readable data layer that ensures every piece of content your company produces, regardless of who or what created it, is anchored in approved positioning.
