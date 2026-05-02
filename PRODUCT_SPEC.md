# MsgStack — Product Specification

**Version:** 0.6  
**Last Updated:** May 2026  
**Status:** Active Development

---

## 1. Problem Statement

Marketing and sales teams at B2B companies spend significant time re-deriving the same positioning and messaging — in pitch decks, emails, LinkedIn posts, battlecards, and one-pagers — because approved messaging frameworks live in disconnected documents that aren't discoverable or machine-readable.

The result:
- AI-generated content drifts from approved positioning because LLMs have no access to the company's actual messaging
- Sales and marketing teams are inconsistent across channels — same product, different story depending on who's talking
- New hires and agencies have no reliable source of truth and freelance the copy
- Marketing ops has no way to know if published content is on-message without reading every piece
- Messaging frameworks sit in PowerPoints or Google Docs, get outdated, and are ignored

MsgStack solves this by making messaging frameworks **structured, searchable, and directly accessible to AI assistants**. The hybrid Knowledge Graph + Vector RAG architecture (now implemented) combines semantic vector search with deterministic graph retrieval — verbatim approved messaging is returned exactly, not approximated by nearest-neighbor search.

---

## 2. Vision

> Messaging as infrastructure: a structured, always-current data layer that any AI assistant, field team member, or agency can generate from — with the confidence that what comes out is anchored in approved positioning, and the visibility to know when it isn't.

The long-term goal is not a content creation tool. It's the **messaging governance layer** for B2B marketing organizations — the system of record for what the company is authorized to say, and the engine that enforces it across every channel, team, and tool.

---

## 3. Target Users

### Primary: Product Marketing & Brand Teams
- Build and maintain Message Houses from source strategy documents
- Define approved positioning, personas, key messages, proof points
- Control which messages are approved for use vs still in draft
- Monitor alignment of generated and published content against the framework

### Secondary: Field Marketing, Sales, Regional Teams
- Self-service artifact generation from approved messaging — no message house editing access
- Access via field portal (URL-based, no admin account required)
- Generate region-specific or persona-specific content that stays on-brand

### Tertiary: Agencies & Contractors
- Receive a scoped, read-only view of the message house for a specific product or campaign
- Generate draft materials from approved messaging that get submitted back for review
- No direct message house access; all generation through the approved message set

### Quaternary: AI Assistants (Claude, ChatGPT, Cursor, Copilot)
- MCP client consuming grounding tools during content generation sessions
- Generate grounded artifacts on demand via `generate_artifact`
- Alignment scoring of drafted content before it's submitted for review

---

## 3.5 Strategic Gaps — What Makes This a Product Marketing Teams Buy

The current build solves a technical problem (AI grounding) well. The features below are what translate that into a product a VP of Marketing will buy and a marketing ops team will actually use. They are listed in order of adoption impact — each one removes a reason a marketing department would say "this isn't for us yet."

### Gap 1 — Alignment Scoring (Most Novel Feature)

MsgStack has a structured message house and can generate from it. What it cannot yet do is evaluate content that already exists — the blog post that went live last quarter, the SDR email sequence, the agency campaign that shipped last month — and score how well it maps to the approved framework.

**Why this is novel:** Nobody else can do this because nobody else has a machine-readable message house to score against. Every other AI writing tool can generate content; none of them can tell you whether existing content is on-brand in a structured, quantitative way.

**What it looks like:**
- Paste any piece of content → receive a per-section alignment score against the active message house
- "This email scores 78% against the CHRO persona messaging. Missing: proof point about efficiency gains. Contradicts: approved positioning on AI."
- Batch scoring: connect your HubSpot or Salesforce content library and run alignment scoring across all published assets
- "Drift report" — generate a weekly report showing which published content has diverged from the message house since the framework was last updated

**What it unlocks:** This is the ongoing reason marketing ops opens MsgStack every week, not just when they need a new asset. It closes the feedback loop between generation and governance.

### Gap 2 — Governance That Can't Be Bypassed

Without approval-gated generation, the message house is advice, not authority. Marketing managers need to be able to mark certain messages as `Draft`, `Under Review`, or `Approved`, and have the generation pipeline refuse to generate from anything that isn't `Approved`. They need to know that field teams and agencies generating from the system are using only cleared messaging — not draft proof points that haven't passed legal review.

**What it looks like:**
- Message-level status: `Draft` | `Approved` | `Outdated` | `Locked`
- Generation refuses to use non-`Approved` messages, surfacing a warning to the user
- Approval workflow: message author submits for review → reviewer approves or comments → status updates → grounding index refreshed
- Drift detection: when the message house is updated, all previously generated artifacts that used the changed messages are automatically flagged as potentially outdated

### Gap 3 — Self-Service Field Portal

The people who most need grounded content are the ones farthest from the message house: SDRs, regional marketers, partner managers, and agencies. They don't need the admin UI. They need to open a URL, pick what they want to create, and get a grounded draft in 30 seconds.

**What it looks like:**
- Shareable portal URL scoped to one or more message houses — no login required, or simple email-based access
- Simplified generation UI: choose artifact type → choose persona (optional) → generate → download or share
- Field users cannot edit the message house, only generate from it
- All generation from the portal is logged against the field user's identifier for audit purposes
- Agency submission mode: generated artifacts are submitted back to the marketing team for approval before use, not immediately downloadable

### Gap 4 — Competitive Intelligence

Battlecards are only useful if they reflect what competitors are actually saying today. MsgStack can generate battlecards from your messaging; it cannot yet help you understand the competitive landscape you're responding to.

**What it looks like:**
- Competitor document import: upload a competitor's website pages, datasheets, or sales decks → the structuring pipeline extracts their message house (headline claims, differentiation, personas targeted, tone)
- Competitor house stored as a `competitive_brief` document type with comparison metadata
- Automatic battlecard sharpening: when generating a battlecard, the system uses the competitor's extracted message house to ensure every response directly counters their actual claims
- Competitor monitoring (stretch): periodic re-fetch of competitor URLs; alert when their messaging has meaningfully changed and battlecard refresh is needed

### Gap 5 — Direct Publishing Integrations

Every artifact generated in MsgStack needs to be copy-pasted into another tool before it reaches the market. That copy-paste moment is where grounding breaks — content gets edited in transit and drifts. Direct publishing integrations close this gap.

**Priority integrations:**
- **HubSpot:** push email templates directly into HubSpot email drafts; push social posts to HubSpot social publish queue
- **LinkedIn:** publish social card artifacts directly to LinkedIn company page or personal profile via LinkedIn API
- **Salesforce:** push approved key messages and battlecard content into Salesforce CRM as content snippet library accessible to reps
- **Google Docs:** export any artifact as a formatted Google Doc into a designated Drive folder (closes the agency collaboration loop)
- **Slack:** slash command `/msgstack generate one-pager HR` — returns grounded content in Slack, no admin UI required

### Gap 6 — Activation Path for Non-Technical Buyers

A marketing manager who is not a developer cannot currently set up MsgStack. The setup requires configuring a Python environment, obtaining a Pinecone API key, setting up a Cloudflare tunnel, and running a server process. This kills adoption at the evaluation stage.

**What "activation in 5 minutes" looks like:**
- Hosted SaaS mode: cloud-hosted instance with no infrastructure to manage (Pinecone, server, DB all managed)
- Onboarding wizard: upload a document → review the extracted message house → generate first artifact → done
- Industry-specific starter templates: pre-built message house skeletons for B2B SaaS, Professional Services, Enterprise Software, Financial Services — so users understand what a complete message house looks like before they build one
- Completeness coaching: the admin UI actively prompts users to fill gaps ("Your house is missing proof points — add 2 to unlock battlecard generation")

### Gap 7 — Built-In AI Chat Interface

Currently the AI experience requires a separate MCP client (OpenWebUI, Claude Desktop). This is a barrier for marketing teams who don't want to configure additional tools. A built-in chat interface in the admin UI removes this barrier.

**What it looks like:**
- Chat panel embedded in the admin UI — model pre-instructed, message house pre-loaded, grounding automatic
- Conversation starters: pre-configured session links ("Generate CHRO-targeted LinkedIn content for the HR house") that any team member can click without setup
- Shareable sessions: send a colleague a link that opens a pre-configured chat context so they can generate without understanding the system
- AI is the primary interaction mode for field teams and agencies; the admin UI is the authoring mode for product marketing

### Gap 8 — Content Analytics

MsgStack knows what messages exist and what artifacts were generated. It does not know which messages are being used, which are being ignored, or which generated artifacts were actually published.

**What it looks like:**
- Message usage heatmap: which key messages appear most frequently in generated artifacts
- "Dead messages": proof points and headlines that have never been used in a generated artifact and may need to be revised or removed
- Artifact engagement: views, downloads, and shares of artifact links (if hosted by MsgStack)
- Generation → publish rate: what percentage of generated artifacts were actually downloaded/exported (proxy for quality)
- Per-persona message coverage: are there personas in the message house that are underserved by the key messages?

---

## 4. Core Capabilities

### 4.1 Message House Specifications

| Section | Required | Purpose |
|---|---|---|
| Summary | Yes | 2-3 sentence overview of the product or service |
| Target Audience | Yes | Buyer and user roles |
| Positioning | Yes | Core statement of what the product is and why it matters |
| Tagline | Yes | ≤7 word punchy headline |
| Differentiation | Yes | Key differentiators |
| Brand Personality | No | Tone, voice, word choices |
| Key Messages | Yes (min 8) | Headlines, benefits, use cases, proof points, objections |
| Personas | Yes (min 1) | Buyer/user personas with triggers and objections |
| Messaging Pillars | No | Strategic theme groupings for key messages |
| Know Your Market | Optional | Research pre-section (vision, before/after, FOMO, competition) |

**Completeness Scoring:** Each framework is scored 0-100 against the spec. The score drives the "Missing Sections" UI and AI-fill prompts.

**Document Types:** The `document_type` field discriminates between framework types: `message_house` (default), `brand_guide`, `competitive_brief`, `corp_narrative`, `persona_library`. All types use the same schema and graph engine.

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
- Prompt maps diverse document formats to the canonical MessageHouse schema
- Persona extraction uses a dedicated second LLM call with `response_format=json_object`
- Output: `StructuredHouse` with all fields, `missing_sections` list, and `personas` with `pain_points`, `buying_triggers`, `objections` as `{statement, response}` pairs

**Stage 3 — Persistence + Indexing**
- SQLite/PostgreSQL: `MessageHouse`, `KeyMessage[]`, `Persona[]`, `MessagingPillar[]` saved via SQLAlchemy ORM
- Pinecone: each message + house fields + KYM block vectorized and upserted (`text-embedding-3-small`, 1536 dims)
- Knowledge Graph: rebuilt in-memory (NetworkX DiGraph) from DB with full entity-relationship structure

### 4.3 Grounding Architecture

Two complementary retrieval layers:

**Vector Layer (Pinecone)**
- Query pipeline: embed → Pinecone query → metadata filter → keyword overlap rerank
- Use case: exploratory queries, thematic similarity, broad searches
- Results approximate by design — "nearest neighbor" semantics

**Graph Layer (NetworkX DiGraph)**
- Query pipeline: graph traversal via typed edges — no approximation
- Use case: governance queries, verbatim approved content, exact taglines and locked proof points
- Node types: `GroundingDocument`, `MessagingPillar`, `GroundingChunk`, `Persona`, `Channel`, `PainPoint`, `BuyingTrigger`, `Objection`
- Edge types: `CONTAINS`, `TARGETS`, `ADDRESSES`, `APPLIES_TO`, `HAS_PAIN_POINT`, `HAS_TRIGGER`, `HAS_OBJECTION`, `RESOLVES`

**Retrieval Mode Routing** (via `retrieval_mode` parameter):
- `vector` — Pinecone semantic search only
- `graph` — Graph traversal for deterministic retrieval
- `hybrid` — Vector first, graph for related context (default)
- `keyword` — SQLite full-text fallback

**Fallback chain:** Vector → Keyword (if Pinecone unavailable). Graph traversal works regardless of Pinecone status.

**Session tracking:** Active house, used chunks, confidence level, persona context.

### 4.4 Artifact Generation

**Grounding contract:** `generate_artifact` loads ALL key messages from the house (grouped by section type, sorted by priority — no caps), ALL personas with complete attributes (pain points, buying triggers, objections), and full brand positioning. A structured grounding block is prepended to every prompt with an explicit instruction: "do not introduce capabilities, statistics, or claims not present here."

**Skill Templates** (`generator.py` + `skills.py`)
- 12 pre-built skill templates stored as JSON in `data/skills/`
- Each skill has a `prompt_template` and `sections` definition
- `_build_context()` builds a structured context block grouping messages by section type with per-group message counts and priority ordering
- GPT-4o-mini fills the template (temperature 0.7, max 4000 tokens)
- Default skill files always written on server start — template improvements land automatically
- Output: `GeneratedArtifact` with raw LLM content + parsed sections dict + full `grounded_messages` list

**Direct Generation** (`web_app.py`)
- Per-section LLM generation for filling missing framework sections
- Used by the "Generate with AI" buttons in the upload flow

### 4.5 Visual Artifacts

#### Current State (v0.6 / early v0.8)

`one_pager` and `one_pager_visual` skills both route to the Fabric.js canvas at `/canvas?artifact_id={id}`. The canvas app renders a basic zone structure (hero, positioning, messages) from the LLM-generated design spec. Output is functional but primitive — no brand system, no professional layout templates, no interactive editing beyond display.

Legacy HTML artifact pages remain at `/artifact/{type}/{house_id}` for `social_posts`, `battlecard`, and `email_sequence`.

#### Target State (v0.8) — What "Done" Looks Like

A generated artifact should be indistinguishable in quality from one a skilled designer produced in Figma, given the same content. Concretely, an HR Service Delivery datasheet generated from the HR messaging house should include:

- A branded header bar with logo zone and product name
- The tagline rendered as a large, prominent headline
- Three differentiator columns each with icon zone, bold headline (6 words max), and 1-2 sentence body
- A grid of the top 6 key messages organized by section type with color-coded labels
- Persona cards for each audience (name, role, 2 bullet pain points) in a horizontal strip
- Optional proof/stat block if proof point messages contain measurable outcomes
- A branded footer with CTA, URL, and logo

This level of output requires all three components to work together: the design system (brand tokens + template definitions), the LLM prompt layer (content-to-zone mapping), and the canvas renderer (zone type implementations + export).

#### Design JSON Schema (v2 — Target)

The v1 schema (`{zones: [{type, text}]}`) is replaced by a structured spec:

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
    {
      "id": "differentiators",
      "type": "pillar_grid",
      "row": 3, "col": 1, "colspan": 12,
      "columns": 3,
      "items": [
        {"icon_type": "automation", "headline": "AI-Powered Automation", "body": "..."},
        {"icon_type": "experience", "headline": "Enhanced Employee Experience", "body": "..."},
        {"icon_type": "strategy", "headline": "Strategic Focus Restored", "body": "..."}
      ]
    },
    {
      "id": "messages",
      "type": "message_list",
      "row": 4, "col": 1, "colspan": 12,
      "columns": 2,
      "items": [
        {"section_type": "Headline", "text": "...", "channel": "all"},
        ...
      ]
    },
    {
      "id": "personas",
      "type": "persona_strip",
      "row": 5, "col": 1, "colspan": 12,
      "personas": [
        {"name": "CHRO", "role": "Chief HR Officer", "pain_points": ["...", "..."]}
      ]
    },
    {
      "id": "footer",
      "type": "cta_footer",
      "row": 6, "col": 1, "colspan": 12,
      "cta": "Learn how ServiceNow can transform your HR operations",
      "url": "servicenow.com/hr",
      "background": "{{brand.primary}}"
    }
  ]
}
```

Brand tokens are resolved at render time from workspace brand settings. Default workspace brand settings apply if none are configured.

#### Default Template Designs

Each artifact type has a defined design DNA. These are the reference layouts implemented by both the LLM prompts and the canvas renderer:

**Datasheet / One-Pager** — Portrait letter. B2B sales motion. High information density.
1. Brand header bar (full-width, brand primary): logo + product name
2. Hero section: tagline (H1) + 1-line positioning (body)
3. 3-column differentiator grid: icon zone + bold headline + 2-sentence body per column
4. Key messages grid (2 columns): top 6 messages grouped by section type with color labels
5. Persona strip: up to 3 personas, each with name/role/2 pain points
6. Proof strip (optional): 3 stat callouts — large number + label
7. CTA footer: call to action + URL + logo

**Battlecard** — Landscape letter. Competitive sales aid. Two-column format.
1. Header: our product name (left) vs competitor (right) + battlecard label
2. Our positioning (full-width)
3. Left column: top differentiators and strengths
4. Right column: common objections + verbatim responses from graph
5. Bottom strip: top 3 proof points + target personas

**Social Card** — Square (1:1) or Story (9:16). Minimal text, bold visual.
1. Full-bleed brand gradient or solid background
2. Single key message headline (max 12 words) — large, centered
3. 1-line supporting context — small, below headline
4. Logo bottom-right + optional URL/handle

**Executive Summary** — Portrait letter. Minimal graphics. C-suite audience.
1. Title + subtitle header
2. Full-width positioning paragraph (slightly larger body)
3. 3 numbered strategic pillars — bold headline + 3-4 sentences each
4. Audience and value table: Persona | Primary Value Delivered
5. Clean footer

#### Content-to-Zone Mapping Rules

The LLM's role in visual generation is copy editing, not data organization. The server pre-assigns messaging house content to zones before the LLM call:

| Zone | Source Field | Selection Rule |
|---|---|---|
| `hero.text_content` | `tagline` | Exact tagline value |
| `hero.subtext` | `positioning` | First 2 sentences |
| `pillar_grid.items[].headline` | `differentiation` | Split by bullet; max 6 words each |
| `pillar_grid.items[].body` | `differentiation` | Supporting sentence for each bullet |
| `message_list.items` | `key_messages` | Top 6 by priority; group by section_type |
| `persona_strip.personas` | `personas` | First 3 by completeness score |
| `proof_block.stats` | `key_messages` where type=`proof_point` | Top 3; must contain a number |
| `cta_footer.cta` | `positioning` | Last sentence rewritten as imperative |

#### Rendering Paths

**Path A — Fabric.js (graphic artifacts):** Canvas-based. Design JSON deserialized into Fabric.js objects. User can edit text (IText), replace logo (Image.fromURL), reorder sections, and export PNG/PDF/SVG. Targets: `datasheet`, `battlecard`, `social_card`, `event_brief`.

**Path B — reveal.js (presentations):** Server renders structured slide JSON to reveal.js HTML via Jinja2. Workspace CSS theme applies brand colors and fonts. Speaker notes generated from grounding context. PDF via browser print engine. Targets: `sales_deck`, `event_presentation`, `executive_readout`.

**Path C — Penpot (design export):** Programmatic artifact creation via Penpot API. Returns an edit link in Penpot for final polish and export at full design fidelity. Targets: artifacts requiring pixel-perfect quality for print or external brand use.

**Renderer routing:** Each skill's `renderer` field (`fabric`, `reveal`, `penpot`) routes `generate_artifact` to the correct path via the `ArtifactRenderer` abstraction.

### 4.6 MCP Server Interface

20+ tools exposed via FastMCP (SSE transport):

**Category: Grounding** — `search_messaging`, `set_active_house`, `get_message_house`, `list_message_houses`, `get_graph_connections`, `compare_houses`, `get_grounding_context`, `reset_conversation`, `list_channels`

**Category: Artifacts** — `generate_artifact`, `build_ui_artifact`, `list_skills`

**Category: Admin** — `check_framework_completeness`, `get_framework_spec`, `list_mcp_tools`, `seed_database`

**MCP Prompts** — `system_instructions` (full operating guide), `quick_start` (new user onboarding)

**Grounding guardrails baked into protocol:**
- `list_message_houses` returns `_next_step` field explicitly directing agents to call `generate_artifact` or `get_message_house` — not to write content from metadata
- `get_message_house` docstring includes "CRITICAL: Do NOT use this data to manually write artifacts — use `generate_artifact` instead"
- `system_instructions` prompt contains "NEVER write the content yourself" rules with trigger word lists

### 4.7 Admin UI

Jinja2 template system (`base.html` + `dashboard.html`) served at `/`. No build step.

**Sections:**
- Dashboard (stats card + graph stats widget)
- Frameworks (list + tabbed detail editor: Overview / Messages / Personas)
- Artifacts (framework selector, skill selector, context inputs, output + visual link)
- Upload (drag-drop → preview → confirm flow)
- Skills (search, create, edit, delete)
- Channels (view and manage channels)
- Graph Explorer (interactive Cytoscape.js canvas with node filtering, type legend, detail panel)
- Settings (API keys, workspaces, token usage)

---

## 5. Integration Points

### MCP Client (Claude, Cursor, ChatGPT, etc.)
- Transport: SSE at `/mcp`
- Prompts: `system_instructions` and `quick_start` discoverable via MCP prompts protocol
- For ChatGPT: explicitly request `system_instructions` prompt at conversation start — ChatGPT does not auto-inject MCP prompts

### Cloudflare Tunnel (production)
- Deployed at `https://mcp.abidc.dev`
- `MSGSTACK_BASE_URL=https://mcp.abidc.dev` controls artifact link base

### OpenAI API
- Structuring: GPT-4o-mini (low temperature for consistency)
- Generation: GPT-4o-mini (higher temperature for creativity)
- Embeddings: text-embedding-3-small (1536 dims)

### Pinecone
- Index: `msgstack-chunks`
- Serverless, AWS us-east-1, cosine metric
- Optional — system degrades gracefully to keyword search without it

---

## 6. Data Flow

```
Upload (file)
  → extract_text()              [pypdf / python-docx]
  → structurer.structure()      [GPT-4o-mini]
  → store.upsert_house()        [SQLite/PostgreSQL]
  → engine.index_house()        [Pinecone + OpenAI embeddings]
  → graph_engine.rebuild()      [NetworkX DiGraph from DB]

MCP search_messaging(query)
  → _embed(query)               [OpenAI]
  → index.query(...)            [Pinecone]
  → _rerank(matches)
  → GroundingResponse

MCP get_graph_connections(house_id)
  → graph_engine.get_connections()  [NetworkX traversal — no LLM, no vector]
  → chunks via typed relationships

MCP generate_artifact(skill_id, house_id)
  → store.get_key_messages()    [ALL messages — no cap]
  → store.get_personas()        [ALL personas with full attributes]
  → _build_context()            [structured block: sections grouped by type + persona detail]
  → grounding preamble + skill template → GPT-4o-mini
  → GeneratedArtifact

GET /artifact/{type}/{house_id}
  → store.get_house()
  → render HTML artifact page
```

---

## 7. Tech Stack

| Layer | Technology |
|---|---|
| MCP Server | FastMCP 3.x (SSE transport) |
| Web API | FastAPI 0.100+ |
| ASGI Server | Uvicorn |
| ORM / DB | SQLAlchemy 2.0 + SQLite (dev) / PostgreSQL (prod) |
| Data Validation | Pydantic 2.0 |
| Knowledge Graph | NetworkX DiGraph (in-process, rebuilt from DB on start) |
| LLM | OpenAI API (GPT-4o-mini) |
| Embeddings | OpenAI text-embedding-3-small |
| Vector DB | Pinecone serverless |
| PDF extraction | pypdf |
| DOCX extraction | python-docx |
| Frontend | Jinja2 templates (base.html + dashboard.html) + vanilla JS |
| Graph visualization | Cytoscape.js |
| Visual artifacts — graphic/canvas | Fabric.js (shell shipped; templates + design system planned v0.8) |
| Visual artifacts — presentations | reveal.js (planned v0.8) |
| Visual artifacts — design export | Penpot API (planned v0.8) |
| Python | 3.11+ |

---

## 8. Constraints

- Pinecone is optional — system degrades gracefully to keyword search; graph traversal always available
- Document text is truncated at 24,000 chars before LLM structuring (multi-chunk for larger documents)
- Artifact HTML is stateless — generated fresh from the store on each request
- Knowledge graph is in-memory (NetworkX) — rebuilt from DB on server start; eventual consistency on writes
- Single SQLite file (`msgstack.db`) — not suitable for concurrent write-heavy load (use PostgreSQL for production)
- Session state is in-memory — lost on server restart

---

## 9. Quality Criteria

A generated artifact is considered "grounded" if:
- All key messages from the active framework were available to the generator (no truncation)
- Full persona context (pain points, triggers, objections) was included in the prompt
- A structured grounding block with explicit "do not invent" instruction was prepended
- No vector approximation path was used for governance-critical content (use graph mode)

A Message House is considered "complete" if:
- All required fields populated (summary, audience, positioning, tagline, differentiation)
- Minimum 2 headlines, 3 benefits, 2 proof points, 1 objection
- At least 1 persona with pain points and buying triggers
- Completeness score ≥ 80

---

## 10. Planned Milestones

### v0.8 — Visual Artifact Engine

Produces professional, brand-accurate visual artifacts. Four interdependent streams:

**Stream 1 — Design System Foundation**
- Design JSON schema v2: page spec, layout grid, expanded zone types (header, hero, pillar_grid, message_list, persona_strip, proof_block, cta_footer), brand token references
- Workspace brand settings: primary/secondary/accent colors, heading/body fonts, logo upload and storage
- Artifact template registry: JSON template definitions for datasheet, battlecard, social card, executive summary

**Stream 2 — Default Template Designs**
- Datasheet: branded header + tagline hero + 3-col differentiator grid + 2-col key messages + persona strip + proof stats + CTA footer
- Battlecard: landscape 2-col Us vs Them with verbatim objection responses from graph
- Social card: full-bleed, single key message, logo
- Executive summary: minimal, 3 numbered pillars, persona-value table

**Stream 3 — LLM Prompt Engineering**
- Rewrites `one_pager_visual` prompt to inject template zone structure so LLM maps content to named zones
- New `datasheet` skill with field-level mapping instructions
- `_build_visual_context()` pre-assigns messaging content to template zones before LLM call — LLM polishes, not organizes
- Pydantic validation of design spec output + fallback fill for missing zones

**Stream 4 — Canvas Renderer (Fabric.js)**
- Zone type renderer functions for all defined zone types
- Grid layout engine from zone row/col/colspan properties
- Brand token resolution from workspace settings
- Interactive editing: text IText, logo drag-and-drop, color override, section reorder
- Export: PNG (2× resolution), PDF (jsPDF), SVG

**Stream 5 — reveal.js** — Slide deck generation for `sales_deck`, `event_presentation`, `executive_readout`

**Stream 6 — Penpot** — Programmatic artifact creation via Penpot API; returns edit link for pixel-perfect polish

See [ROADMAP.md](ROADMAP.md) for full task breakdown.

### v0.9 — Document Source Integrations

- **Google Drive (partial ✅):** OAuth2 connector, background sync loop, DOCX native support shipped. Remaining: Drive Picker UI, sync status badges, conflict diff UI
- **OneDrive & SharePoint:** Microsoft MSAL auth, SharePoint document library watch, Microsoft Graph webhooks for real-time sync, Word Online native extraction
- **SourceConnector abstraction:** Pluggable interface enabling Notion, Confluence, and Box without touching core pipeline
- **Sync dashboard widget:** All connected sources, per-framework status, retry controls
