# MsgStack — Product Roadmap

**Last Updated:** May 2026  
**License:** Apache 2.0 — open source, self-hostable  
**Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md)

## Product Framing: The Canon Layer

MsgStack is the **canon layer** for the organization. Departments own their domains of truth. AI tools and content workflows ground on that canon. When canon changes, downstream outputs stay aligned.

MsgStack begins with product marketing because that is the highest-value first wedge. However, the underlying model is designed as an organizational canon layer. This roadmap maps the path to full cross-department canon domains owned by SMEs in Product (including core spec, API, and technical document owners), Marketing, Legal, HR, Support, and Security.

### Grounding Types — The Multi-Department Vision

Each department gets a **Grounding Type**: a schema that defines how their knowledge is structured into queryable canon. The three priority schemas are:

| Grounding Type | Department | Status |
|----------------|------------|--------|
| **Message House** | Product Marketing | ACTIVE — flagship schema, fully implemented |
| **Engineering Spec** | Engineering | PLANNED — v1.0 |
| **Policy Shield** | Legal & Compliance | PLANNED — v1.0 |

Message House is the wedge. Engineering Spec and Policy Shield are the proof that this is an organizational canon layer, not a PMM tool. They are documented on the public website at [msgstack.ai/message-house](https://www.msgstack.ai/message-house) and are the primary v1.0 development targets.

This roadmap reflects the current state and planned direction. Items are grouped by milestone, not calendar quarter — sequencing depends on community feedback and priority shifts. Items marked `[OSS]` are well-suited for community contribution.

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
- ✅ **Tabbed Domain Detail:** Overview (editable), Entries (color-coded, drag-to-reorder), Personas tabs
- ✅ **Skill Context Inputs:** Skills requiring context surface input fields before generation
- ✅ **Multi-Content-Type:** `document_type` discriminator with color-coded badges
- ✅ **Knowledge Graph Engine:** NetworkX DiGraph — deterministic retrieval via typed entity relationships
- ✅ **Graph Explorer UI:** Interactive Cytoscape.js canvas with node filtering and detail panel
- ✅ **Extended Graph Entities:** CanonPillar, PainPoint, BuyingTrigger, Objection as first-class graph nodes
- ✅ **`get_graph_connections` MCP Tool:** Deterministic graph traversal bypassing vector approximation
- ✅ **Full-Context Grounding:** ALL canon entries + ALL persona attributes in every artifact prompt
- ✅ **Grounding Guardrails:** `list_canon_domains` MANDATORY_NEXT_ACTION field directing agents to call tools
- ✅ **Google Drive Sync:** Background sync loop with DOCX/PDF native format support
- ✅ **Fabric.js Canvas Shell:** `/canvas` route + basic `one_pager_visual` skill + design JSON → canvas rendering (primitive — foundation only)
- ✅ **Canvas Routing:** `one_pager` skill now routes to `/canvas?artifact_id=...` instead of static HTML
- ✅ **Turbovec Local Vector DB** (`v0.8.1`): replaced Pinecone with in-process quantized vector search — zero external dependencies, <0.1ms query latency
- ✅ **Automatic Markdown Translation Layer** (`v0.8.2`): high-fidelity DOCX/PDF proxy files saved to `data/sources/{id}.md` and indexed under `source_markdown` section type for full-content RAG including tables and complex formatting

**Known gaps and active issues:**
- Visual artifact output is primitive — canvas renders basic zones without professional layout, brand system, or template design
- `one_pager` skill prompt produces truncated/incomplete section content in some cases
- Design JSON schema is too simple (hero/positioning/entries only) — no brand tokens, column grid, or icon zones
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
- [x] **Approval Workflow:** Mark Canon Entries as `Draft` or `Approved`; grounding prioritizes `Approved`
- [x] **Locking:** Prevent editing of "Core Canon" once approved
- [x] **Artifact Status:** Lifecycle tracking: `Draft` → `Internal Review` → `Approved`
- [x] **Staleness Alerts:** "Last Reviewed" timestamp per framework; flag domains older than 90 days
- [x] **Review Trail:** Log of who reviewed/approved updates and when

### Feedback Loop
- [x] **Content Ratings:** Rate generated artifacts (1-5 stars) or Good/Bad tags
- [x] **Self-Correction:** Boost relevance for entries used in high-rated artifacts
- [x] **Usage Heatmap:** See which parts of the canon domain are used most vs ignored

---

## v0.8 — Visual Artifact Engine

**Goal:** Produce professional, brand-accurate visual artifacts from canon domain data. This is a full design engineering effort — not just a rendering fix. Three interdependent work streams must come together: a design system that defines what artifacts look like, an LLM prompt layer that generates rich structured design specs from messaging content, and a canvas renderer capable of faithfully executing those specs.

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
  - `message_list` — labeled list of canon entries, optionally grouped by section type
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
4. **Key Messages section**: 2-column grid of message cards. Each card has a section-type label (Headline / Benefit / Use Case / Proof Point), the entry text, and an optional channel tag. Grouped by priority — top 6 entries shown.
5. **Audience section**: Horizontal strip with persona cards. Each card: persona name + role title + 2 bullet pain points. Up to 3 personas. If more exist, truncate to fit.
6. **Proof / Social Proof strip** (optional): 3 stat blocks in a row — large number + label (e.g., "40% reduction in HR case volume"). Omit if no stats in the messaging house.
7. **CTA Footer** (full-width, brand primary): One-line CTA statement + URL + logo small

**Typography:** Heading font for headlines, body font for supporting copy. Font sizes: H1 36pt, H2 22pt, H3 16pt, body 11pt, caption 9pt.

**Color use:** Brand primary for header/footer/accent. Brand secondary or light neutral for differentiator grid background. White or off-white for body sections. Section labels in brand accent color.

- [x] **Design spec JSON for datasheet template** — codify the above as a `data/templates/datasheet.json` template definition
- [x] **LLM mapping logic** — define which canon domain fields map to which zones: `tagline → hero headline`, `positioning → hero body`, `differentiation bullets → pillar_grid`, `top 6 key messages by priority → message_list`, `personas → persona_strip`, `proof points → proof_block`

#### 2b. Battlecard Template

Landscape orientation. Competitive sales aid. Two-column structure: "Us" vs "Them" or "Us" vs "Objection + Response."

**Layout:**
1. **Header**: Product name left, competitor name right, battlecard label center
2. **Positioning row** (full-width): Our one-line positioning
3. **2-Column grid** — left column: key differentiators and strengths; right column: common objections with verbatim responses from canon domain
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
- [x] **LLM mapping logic** — select highest-priority entry for the target channel; apply channel-specific tone

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

The current `one_pager_visual` prompt asks the LLM to "return a JSON object" with minimal guidance. This stream rewrites the generation path so the LLM produces rich, accurate, brand-ready design specs.

#### 3a. Skill Prompt Rewrites

- [x] **`one_pager_visual` prompt rewrite:** Inject the template zone structure into the prompt so the LLM maps canon content to specific zones by name. Include field-level instructions ("tagline → hero.text_content; keep under 10 words"), output format examples with realistic content, and a grounding reminder ("use only content from the canon domain — no invented statistics").
- [x] **New `datasheet` skill:** Separate from `one_pager_visual`. Uses the datasheet template. Prompt instructs the LLM to populate each zone from the correct canon source field. Section-type priority rules baked in (Headline entries → pillar headlines; Benefit entries → pillar bodies; Proof Point entries → proof_block stats).
- [x] **`battlecard_visual` prompt:** Populates battlecard template zones. Requires competitor name. Pulls objections + responses from graph for verbatim accuracy.

#### 3b. Content-to-Zone Mapping Engine

The LLM shouldn't have to figure out which entry goes in which zone on its own — the context block should do this work.

- [x] **`_build_visual_context()` function:** Extend `generator.py` with a visual-specific context builder that pre-assigns canon content to template zones before the LLM call.
- [x] **Priority-based selection:** When a zone has a capacity constraint (e.g., pillar_grid shows 3 items, proof_block shows 3 stats), `_build_visual_context()` pre-selects the highest-priority candidates before passing them to the LLM.
- [x] **Persona truncation rules:** Persona strip shows max 3 personas. Selection order: primary persona first, then by completeness score (most complete pain points + triggers shown first).

#### 3c. Design Spec Validation

The LLM output must be validated before it reaches the renderer. Malformed specs cause silent rendering failures that are hard to debug.

- [x] **Pydantic schema for design spec:** `DesignSpec`, `Zone`, `ZoneContent` models — validate LLM output before saving; auto-fill missing optional fields with template defaults
- [x] **Fallback fill:** If LLM omits a required zone, the validator injects the template default content (pulled from the canon domain directly)
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
- [ ] **Data Mapping Fixes:** Resolve `{placeholder}` leaks (e.g. `{proof_point}`, `{domain_name}`) failing to properly interpolate grounded data before reaching the canvas render engine.
- [ ] **High-Impact Templates (5-10):** Design and implement highly polished, premium aesthetic JSON template schemas (e.g., Executive 1-Pager, Product Tear-Sheet, Capability Brief, ROI One-Pager, Persona Profile, Feature Release, Case Study).
- [ ] **Premium Typography & Styling:** Implement modern, premium typography sets, drop shadows, border radiuses, and glassmorphism token support within the Canvas engine.

---

### Shared Infrastructure (v0.8)
- [ ] **`ArtifactRenderer` abstraction:** Common interface (`render_html`, `render_fabric`, `render_reveal`, `render_penpot`) — new rendering targets added without touching `generate_artifact`
- [ ] **Renderer routing via skill metadata:** `renderer` field on each skill.

---

## v0.9 — Organizational Canon Governance Layer

**Goal:** Turn MsgStack into the organizational canon governance layer, not just a generation tool. This milestone introduces the features that give compliance and brand owners a reason to open MsgStack every week — ensuring all content is verified against approved truth.

### Alignment Scoring
The core governance capability. Evaluates any piece of content against the structured canon domains and returns a per-section alignment report. Possible only because the canon is machine-readable and semantically indexed.

- [ ] **`score_alignment` API endpoint:** Accepts arbitrary text + domain_id; returns per-section scores (0–100) plus specific gaps, out-of-date facts, and contradictions against approved canon entries
- [ ] **Distinguish Hard vs. Soft Conflicts:** Classify alignment gaps between factual/positioning contradictions (hard) and subjective/stylistic deviations (soft)
- [ ] **`score_alignment` MCP tool:** AI assistants can score a draft before submitting it — "check this product release summary against the product spec canon domain before I publish"
- [ ] **Alignment report UI:** Paste content into the admin UI → receive color-coded alignment breakdown with specific suggestions ("Missing: proof point about efficiency. Contradicts: positioning on AI autonomy.")
- [ ] **Export to External Parties:** Ability to export annotated comments, highlights, and alignment scores back to external partners (e.g., PR agency drafts) for revisions
- [ ] **Batch scoring:** Connect a CRM or Google Drive folder → score all assets against the active canon → report sorted by alignment score
- [ ] **Drift report:** Weekly summary of all generated artifacts that have diverged from the canon domain since the source document was last updated
- [ ] **Alignment score on artifact history:** Every saved artifact record shows its alignment score at time of generation; re-scored automatically when the parent canon is updated

### Canon Approval & Suggestion Workflows
- [ ] **Canon entry status field:** `Draft` | `In Review` | `Approved` | `Outdated` | `Locked` on every canon entry, persona, and domain field
- [ ] **Approval-gated grounding:** `generate_artifact` and grounding search skip non-`Approved` canon entries by default; optional `include_drafts` override for editing/staging sessions
- [ ] **Element-Level RBAC:** Every atomic element has defined owners and collaborators, supporting 4 permission levels: *Owner*, *Collaborator*, *Suggester*, and *Viewer*
- [ ] **Suggestion Flow Routing:** Users without edit authority can only make suggestions, which automatically route to designated owners for approval
- [ ] **Conflict Review Sets:** Automated change notifications and conflict review packages sent to downstream owners when a parent element is edited (support accept, decline, suggest, or escalate options)
- [ ] **Review request flow:** Domain author marks an entry as "Ready for Review" → domain owner receives notification → approves or comments → status updates → vector index refreshed
- [ ] **Drift detection:** When a canon entry is updated, all artifact history records that used it are flagged as potentially outdated
- [ ] **Locked canon:** "Core Canon" locked status prevents any edits without admin or designated SME override; graph retrieval always returns locked entries verbatim
- [ ] **"Gold Standard" Content Designation:** Flag specific generated deliverables as the canonical reference version that all other related content should conform to

### Self-Service Canon Consumption Portal
- [ ] **Portal URL per workspace:** Shareable link (no admin account required) scoped to specific approved canon domains
- [ ] **Simplified generation UI:** Persona selector → artifact type selector → optional context inputs → generate → download/share
- [ ] **Content-only access:** Portal users cannot view or edit the source canon; they only generate derived artifacts from approved entries
- [ ] **Agency submission mode:** Generated drafts are held in a pending queue for SME approval.
- [ ] **Portal analytics:** Log all field portal generation activity for audit and usage insight.

### Temporary Message Layer
- [ ] **Leadership Message Overlay:** Support injecting a high-priority "temporary layer" message above the canon for a defined timeframe (without permanently modifying database records)

### Content Tiering (Generation Contract)
Lifecycle status says whether an entry is ready; tier says how an LLM may use it. Orthogonal to `Draft`/`Approved`/`Locked` — the per-entry contract that makes "verbatim means verbatim" enforceable.

- [ ] **`tier` field on Canon Entries:** `tier_1_locked` (verbatim, no paraphrase) | `tier_2_structured` (substance preserved, phrasing adaptable) | `tier_3_grounded` (spirit and tone, full latitude)
- [ ] **Tier enforcement in generation:** `generate_artifact` grounding block carries per-entry tier directives; Tier 1 entries injected with an explicit reproduce-verbatim instruction and validated post-generation
- [ ] **Tier-aware retrieval routing:** Tier 1 always served via graph traversal (deterministic), never vector nearest-neighbor; Tier 2 hybrid; Tier 3 vector
- [ ] **Tier tagging gate:** entries cannot transition to `Approved` without a tier assignment (validated at promotion)
- [ ] **Alignment integration:** a paraphrased Tier 1 entry classifies as a hard conflict in alignment scoring
- [ ] **Tier tagging UI:** tier selector on entry editor + bulk tier assignment; tier badge in entry lists and grounding results

### Content SLA & Freshness Triggers
Replaces the static 90-day staleness flag with a per-domain operational contract for freshness.

- [ ] **Per-domain review cadence config:** each domain declares its own review interval (quarterly positioning, per-release competitive claims, etc.)
- [ ] **Trigger events API:** register events (product release, competitive move, market shift) via API/webhook that open an SLA review window on affected domains regardless of cadence
- [ ] **SLA-breach notifications:** review window closes without a review → domain owner and DRIs notified, domain flagged `needs_review`
- [ ] **SLA dashboard:** admin view of every domain's SLA state (in-window / due / breached) with last-reviewed dates and open trigger events

### DRI Ownership
- [ ] **`dri` field on Canon Entries and Domains:** the named person accountable for a claim — distinct from `approved_by`
- [ ] **Ownership transfer flow:** reassign DRI on team changes with a logged transfer event
- [ ] **Accountability view:** dashboard of entries/domains per DRI, surfacing unowned entries and SLA state per owner

### Dual Output — Citation-Marked Review Copy
- [ ] **Two renditions per generated artifact:** a review copy with inline chunk-level citations (source entry, source doc, tier, DRI, last-reviewed date) and a clean deliverable with no citation clutter
- [ ] **Linked citations:** each citation in the review copy links to the canon entry in the admin UI
- [ ] **Reviewer workflow:** review copy is the artifact reviewers validate before the clean deliverable ships

### Query Audit Log
- [ ] **Retrieval-side audit:** log every grounding query (MCP + web) — caller identity, query text, entry IDs returned, confidence scores, timestamp
- [ ] **Admin audit view:** filterable log with export
- [ ] **Downstream feeds:** audit log powers acceptance-signal analytics (v1.3) and identity-scoped retrieval auditing (v1.0)

---

## v1.0 — Cross-Department Canon & Dependency Graphs

**Goal:** Expand MsgStack from a marketing-only message house repository to a cross-department canon layer. Product, Legal, HR, and Security teams can curate and connect their respective domains of truth.

### Cross-Department Canon Domains & Hierarchy
- [ ] **Dynamic Grounding Schemas:** Support dynamic Pydantic/JSON Schema validation per domain, allowing custom schemas by department beyond just the default `message_house` layout.
- [ ] **`engineering_spec` Grounding Type:** API constraints, system SLAs, versioning policy, deprecation notices, security requirements. Keeps developer copilots aligned with real specs — not hallucinated rate limits.
- [ ] **`policy_shield` Grounding Type:** Legal disclaimers, privacy policy rules, compliance assertions (SOC2/GDPR), pre-approved compliance responses. AI tools retrieve legal language verbatim — no paraphrasing.
- [ ] **Sub-Canons ("Canons within Canons"):** Nested canons representing divisions, product lines, or functions with configurable parent-child inheritance.
- [ ] **Inheritance Relationship Types:** Codify 4 parent-child relationship types: *Full Inheritance*, *Selective Override*, *Autonomy with Vocabulary Constraints*, and *Complete Autonomy*.
- [ ] **Canon Health Scoring:** Dashboard view exposing a proprietary metric showing where narrative coherence and graph connections are breaking down.

### Canon Domain Ownership & Live Bindings
- [ ] **Department SME Owners:** Assign read/write permissions to specific department wrappers (e.g., HR Team owns HR Domain, Legal Team owns Legal Domain).
- [ ] **Review Trails:** Changes to a domain must be signed off by designated owners, creating a secure compliance audit trail.
- [ ] **Bindings Layer:** Implement a dynamic mapping system connecting specific organizational canon elements to specific downstream content outputs to enable live update propagation.

### Multi-Domain Dependency Graph
- [ ] **`INFORMS` / `DEPENDS_ON` Edges:** Define explicit graph relationships between different canon domains (e.g., Product Specifications `INFORMS` Product Marketing Messaging, which `INFORMS` Sales Objection Handlers, which `INFORMS` Legal Disclosures).
- [ ] **Cascade Drift Detection:** When a parent canon entry is updated, all downstream messaging and generated battlecards are automatically flagged as "Outdated" and trigger alerts to respective owners.

### Content CI/CD Promotion Pipeline
Treat canon promotion like a code merge. Wires the existing approval workflow, completeness scoring, index refresh, and review trail into one gated pipeline.

- [ ] **Stage 1 — Validate:** automated checks on Draft→Approved promotion: schema compliance, tier tagging present, required metadata (DRI, section type, personas) complete. Failed validation blocks promotion and returns a structured error to the owner.
- [ ] **Stage 2 — Test:** golden query dataset runs against the updated content; retrieval precision/recall measured against baseline; below-threshold scores block promotion
- [ ] **Stage 3 — Merge:** content passes → status transitions, vector + graph index update within the sync window
- [ ] **Stage 4 — Propagate:** downstream propagation signal to all bindings, artifacts, and dependent domains referencing the updated content
- [ ] **Stage 5 — Audit:** promotion event logged — owner, timestamp, entry, validation results, alignment score delta, downstream consumers notified

### Golden Query Dataset & Retrieval Benchmarking
- [ ] **Per-domain golden query set:** curated benchmark queries with expected results (target 100+ per major domain)
- [ ] **Baseline measurement:** precision/recall snapshot per domain; re-run on every index update
- [ ] **Corpus health monitoring:** aggregate score trends per domain; degrading scores trigger a domain owner review
- [ ] **CI/CD integration:** the golden set is the test stage of the promotion pipeline

### Identity-Scoped Retrieval (pulled forward from v1.6)
Embargoed or pre-announcement content must never surface outside its authorized audience — workspace API keys are not enough for cross-department canon.

- [ ] **SSO / OIDC login:** SAML/OIDC (Google, Okta, Azure AD) — moved up from v1.6 Auth & Identity
- [ ] **Per-user retrieval scoping:** grounding queries filter results by the caller's `ElementPermission` grants (role, department, segment)
- [ ] **Embargo scoping:** entries/domains flaggable as restricted-audience; excluded from retrieval, search, and generation for unauthorized users
- [ ] **Scoped MCP identity:** MCP sessions carry user identity so per-user scoping applies to AI-client queries, not just the web UI

---

## v1.1 — Ingestion Expansion & Templates

**Goal:** Broaden ingestion capabilities, expand templates, and integrate competitive market data to sharpen grounding.

- [ ] **Decks, Spreadsheets, & Rich Format Ingestion:** Ingestion adapters for PowerPoint (.pptx), Excel (.xlsx), audio transcripts, voice memos, and unstructured notes.
- [ ] **Render-Mode Tagging:** Ingested assets (slides, quotes, compliance-approved blocks) tagged `render_whole` (insert verbatim exactly as authored) or `read_as_content` (parse as structured input for generation). Complements Tier 1 for legally-reviewed visual assets.
- [ ] **Industry/Segment Variant Dimension:** `industry` tag on canon entries and personas as a first-class variant axis (persona × channel × industry); retrieval filters and variant selection honor it.
- [ ] **Deck Indexing & Presentation Assembly:** Index existing approved decks (not just generate new ones); surface relevant slides on query; presentation assembly skill structures a new deck outline from approved slides + canon entries.
- [ ] **Audio/Video Indexing:** Segment classification at ingest (keynote, demo, testimonial); timestamped moment retrieval so queries surface the relevant clip, not the whole transcript.
- [ ] **Ingestion Conflict Detection:** Scan uploaded files and flag contradictions against existing canon elements before committing changes.
- [ ] **50+ Pre-built Deliverable Templates:** Derive templates from real client work (CEO keynotes, sales decks, battlecards, press releases, investor updates, product messaging frameworks, etc.).
- [ ] **Competitor document import:** Upload competitor docs → extraction pipeline extracts claims into a `competitive_brief` domain
- [ ] **Competitive gap analysis:** Compare your canon domain to a competitor's extracted claims — identify where you are differentiated vs where they challenge you
- [ ] **Battlecard auto-sharpen:** Automatically load the competitor's extracted claims and ensure each response directly counters their stated positioning using approved canon entries

---

## v1.2 — Publishing Integrations

**Goal:** Close the gap between "generated" and "published."

- [ ] **HubSpot integration:** Push email templates to drafts; push social posts to HubSpot publish queue; pull assets for alignment scoring
- [ ] **LinkedIn integration:** Publish social card artifacts to company page or personal profile; pull posts for alignment scoring
- [ ] **Salesforce integration:** Push approved key messages and battlecards into Salesforce CRM as opportunity snippets
- [ ] **Google Docs export:** Export any artifact as a formatted Google Doc into a designated Drive folder
- [ ] **Slack app:** `/msgstack generate one-pager` slash command returns grounded content in Slack
- [ ] **Webhook outbound:** Send any generated artifact to any external system via POST

---

## v1.3 — Agentic Ingestion & Custom Controls

**Goal:** Layer specialized AI agents and narrative controls over the ingestion and generation pipeline.

### Onboarding & Activation
- [ ] **Hosted SaaS mode:** Cloud-hosted managed instance with database, vector index, and server
- [ ] **Onboarding wizard:** Upload document → review extracted canon domain → generate first artifact → share link
- [ ] **Industry starter templates:** Pre-built skeletons for B2B SaaS, Professional Services, IT, etc.
- [ ] **Completeness coaching:** Admin UI actively prompts to fill gaps with value-add suggestions
- [ ] **Sample domains:** Loads a pre-built demo domain to explore generation before ingestion

### Agentic Layer & Interface
- [ ] **Specialized AI Agents:** Functional agents for Governance, Brand Voice, and Narrative Structure analysis.
- [ ] **Canon Navigator:** Conversation-first dashboard super agent to query changes, review narrative drifts, and request summaries ("what changed recently and how does it affect my work?").
- [ ] **Recommendation Routing:** Agent analyses of incoming material suggesting where it fits in the canon, what downstream deliverables are affected, and highlighting contradiction conflicts (supporting auto-accept or manual confirmation toggles).
- [ ] **Proactive Human-in-the-Loop Governance:** Integration points prompting review at appropriate gates.
- [ ] **Intent-Based Routing & Model Selection:** Classify query intent and route to the appropriate model tier (cheap model for simple retrieval, strong model for synthesis/generation) and the right skill or skill chain — removes model and skill selection burden from the user. Pairs with the multi-LLM backlog item.

### Custom Controls & Brief Builder
- [ ] **Tonal Slider Controls:** Adjust tone register (e.g. formal IR presentation vs. conversational social post) while staying within brand voice boundaries.
- [ ] **Controlled Vocabulary Filters:** Avoid competitor-associated phrasing, and flag or filter out banned terms in deliverables.
- [ ] **Brief Builder Interface:** Build context inputs directly into deliverable creation wizard to guide LLM assembly.
- [ ] **Source Annotations:** Automatically tag generated deliverables with source citations mapping directly back to specific grounded canon entries.
- [ ] **Localization Skill:** Adapt generated output for regional markets — tone, cultural references, market context — with the brand voice check running as a QA gate on the localized output.

### Content Analytics
- [ ] **Canon usage heatmap:** Which canon entries appear most in generated artifacts to prune dead content
- [ ] **Artifact engagement:** Views, downloads, and shares of hosted links
- [ ] **Acceptance Signals:** Capture saved / exported / published events per generated artifact as explicit acceptance telemetry
- [ ] **Value Reporting:** Periodic report from acceptance telemetry + query audit log — executions per skill, acceptance rate, estimated hours saved (hours saved × executions × acceptance rate × blended rate)

---

## v1.4 — Document Source Integrations

**Goal:** Connect MsgStack directly to where team documents live, syncing canon domains automatically as source files evolve.

### Google Drive Integration
- ✅ OAuth2 Connector
- ✅ Background sync loop for changed files
- ✅ DOCX native format support
- [ ] **Drive Picker UI:** Embed Google Drive file picker in the Upload section
- [ ] **Sync status UI:** "Source in Drive" badge; "outdated" warning when Drive file is newer
- [ ] **Conflict diff UI:** Show structured diff before re-ingestion

### OneDrive & SharePoint Integration
- [ ] **Microsoft MSAL Auth:** OAuth2 PKCE flow for OneDrive and SharePoint
- [ ] **OneDrive Folder Watch:** Auto-ingest trigger
- [ ] **SharePoint Document Library Watch:** Monitor SharePoint libraries
- [ ] **Microsoft Graph Webhooks:** Real-time change notifications
- [ ] **Word Online Documents:** Native extraction via Microsoft Graph

### Source Sync Infrastructure
- [ ] **SourceConnector Abstraction:** Pluggable connector interface (`connect()`, `watch()`, `fetch()`, `push()`) for Notion, Confluence, etc.
- [ ] **Sync Dashboard Widget:** Panel showing connected sources, sync status, and manual re-sync triggers

---

## v1.5 — Advanced Graph Operations & Visualization

### Graph-Powered Queries
- [ ] **Persona Coverage Analysis:** Identify which canon entries address which personas and flag coverage gaps
- [ ] **Channel Reachability:** Which channels can a claim reach through relationships?
- [ ] **Cross-Domain Comparison:** Compare claims and relationships across multiple domains

### Cross-Document Intelligence
- [ ] **GroundingCollection:** Bundle multiple documents into a named collection
- [ ] **INFORMS Edge:** Traverse relationship paths back to source-of-truth documents

### Graph Maintenance
- [ ] **Neo4j Migration Path:** Enable Neo4j adapter for high scalability

---

## v1.6 — Platform & Ecosystem

### Additional Integrations
- [ ] **Notion connector** — Sync domains to/from Notion pages
- [ ] **Confluence connector** — Watch a Confluence space for source documents

### Auth & Identity
- ~~**SSO integration** — SAML/OIDC (Google, Okta, Azure AD)~~ → **Moved to v1.0** (Identity-Scoped Retrieval)

### Advanced Search & Governance
- [ ] **Cross-domain search** — "What do all our product teams say about security?"
- [ ] **Audit Trail & Logging:** Detailed logging: what changed, when, who changed it, their authority/permission level, and which department wrapper they belong to.
- [ ] **User Experience Dashboard:** Personalized dashboard per user showing narrative announcements, activities, pending suggestions, and permissions metrics.

---

## Backlog (Unscheduled)
- Multi-LLM support (Anthropic Claude, Gemini, local Ollama)
- CLI tool (`msgstack search "..."`)
- VS Code extension for inline claims suggestions
- Print-First Documents via Paged.js (typeset PDFs with real margins and bleed)

---

## What We're Not Building
- A full CMS or editorial calendar
- A social media scheduling tool
- A CRM or design tool

MsgStack is **organizational canon infrastructure** — the structured, machine-readable data layer that ensures every piece of content your company produces, regardless of who or what created it, is anchored in approved truth.
