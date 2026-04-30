# MsgStack — Product Specification

**Version:** 0.6  
**Last Updated:** April 2026  
**Status:** Active Development

---

## 1. Problem Statement

Marketing and sales teams at B2B companies spend significant time re-deriving the same positioning and messaging — in pitch decks, emails, LinkedIn posts, battlecards, and one-pagers — because approved messaging frameworks live in disconnected documents that aren't discoverable or machine-readable.

The result:
- AI-generated content drifts from approved positioning because LLMs have no access to the company's actual messaging
- Sales and marketing teams are inconsistent across channels
- New hires and agencies have no reliable source of truth
- Messaging frameworks sit in PowerPoints or Google Docs, get outdated, and are ignored

MsgStack solves this by making messaging frameworks **structured, searchable, and directly accessible to AI assistants**. The hybrid Knowledge Graph + Vector RAG architecture (now implemented) combines semantic vector search with deterministic graph retrieval — verbatim approved messaging is returned exactly, not approximated by nearest-neighbor search.

---

## 2. Vision

> Marketing messaging as an always-current, machine-readable layer that any AI assistant or marketing tool can ground against — ensuring that every generated artifact, from a 280-character tweet to a full press release, is anchored in approved positioning.

---

## 3. Target Users

### Primary: Marketing Strategists & Content Teams
- Build and maintain Message Houses
- Upload source documents (strategy decks, product briefs, analyst reports)
- Generate and review grounded marketing artifacts
- Maintain framework completeness and quality

### Secondary: AI Assistants (Claude, ChatGPT, Cursor)
- MCP client consuming grounding tools during content generation sessions
- Use frameworks to search for relevant messaging before generating
- Generate grounded artifacts on demand via `generate_artifact`

### Tertiary: Sales & Field Teams
- Access messaging through AI assistants or shareable artifact URLs
- Use battlecards and one-pagers generated from the latest frameworks
- No direct UI interaction required

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

Standalone HTML pages served at `/artifact/{type}/{house_id}`:

| Type | URL | Contents |
|---|---|---|
| `one_pager` | `/artifact/one_pager/{house_id}` | Dark hero + positioning card + color-coded message grid + persona cards |
| `social_posts` | `/artifact/social_posts/{house_id}` | LinkedIn, Twitter, email post cards with channel tags |
| `email_template` | `/artifact/email_template/{house_id}` | Awareness + consideration + decision email stages |

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

## 10. Planned: Google Drive & OneDrive/SharePoint Integration (v0.8)

The next major milestone connects MsgStack to the document sources marketing teams already use. See [ROADMAP.md](ROADMAP.md) for the full feature breakdown. Key capabilities planned:

- **Google Drive:** OAuth2 connector, folder watch with auto-ingest, Drive Picker UI, sync status badges, conflict diff UI, optional push-back-to-Drive
- **OneDrive & SharePoint:** Microsoft MSAL auth, SharePoint document library watch, Microsoft Graph webhooks for real-time sync, Word Online native extraction
- **SourceConnector abstraction:** Pluggable interface enabling Notion, Confluence, and Box integrations without touching the core pipeline
- **Sync job queue:** SQLite-backed background queue with a dashboard panel showing sync status, failures, and retry controls
