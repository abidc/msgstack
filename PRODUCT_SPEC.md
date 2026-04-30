# MsgStack — Product Specification

**Version:** 0.2  
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

MsgStack solves this by making messaging frameworks **structured, searchable, and directly accessible to AI assistants**. The v0.7 milestone will deepen this with a hybrid Knowledge Graph + Vector RAG architecture — combining semantic vector search with deterministic graph retrieval so that verbatim approved messaging (taglines, locked proof points, approved headlines) is returned exactly, not approximated by nearest-neighbor search.

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
- Generate grounded artifacts on demand

### Tertiary: Sales & Field Teams
- Access messaging through AI assistants or shareable artifact URLs
- Use battlecards and one-pagers generated from the latest frameworks
- No direct UI interaction required

---

## 4. Core Capabilities

### 4.1 Message House Specifications

| Section | Required | Purpose |
|---|---|---|
| Summary | Yes | 2-3 sentence overview of the product or service. |
| Target Audience | Yes | Buyer and user roles. |
| Positioning | Yes | Core statement of what the product is and why it matters. |
| Tagline | Yes | ≤7 word punchy headline |
| Differentiation | Yes | Key differentiators |
| Brand Personality | No | Tone, voice, word choices |
| Key Messages | Yes (min 8) | Headlines, benefits, use cases, proof points, objections |
| Personas | Yes (min 1) | Buyer/user personas with triggers and objections |
| Know Your Market | Optional | Research pre-section (vision, before/after, FOMO, competition) |

**Completeness Scoring:** Each framework is scored 0-100 against the spec. The score drives the "Missing Sections" UI and AI-fill prompts.

### 4.2 Document Ingestion Pipeline

Three-stage pipeline triggered on file upload:

**Stage 1 — Text Extraction** (`extract.py`)
- PDF: `pypdf`, page-by-page
- DOCX: `python-docx`, paragraphs + tables
- TXT/MD: utf-8 / latin-1 / cp1252 fallback chain
- Output: raw text string

**Stage 2 — LLM Structuring** (`structure.py`)
- Model: GPT-4o-mini (temperature 0.3, max 4000 tokens)
- Input: up to 24,000 chars of raw text
- Prompt instructs the LLM to recognize diverse document formats (Know Your Market, Value Pillars, Use Cases, Proof Points table, Elevator Pitch, etc.) and map all of them to the canonical MessageHouse schema
- Output: `StructuredHouse` with all fields and `missing_sections` list

**Stage 3 — Persistence + Indexing**
- SQLite: `MessageHouse`, `KeyMessage[]`, `Persona[]` saved via SQLAlchemy ORM
- Markdown: full framework rendered to `data/frames/{id}.md`
- Pinecone: each message + house fields + KYM block vectorized and upserted (model: `text-embedding-3-small`, 1536 dims)

### 4.3 Grounding Search

Hybrid search combining vector semantics with structured metadata filtering.

**Query pipeline:**
1. Natural language query → infer section_type / persona / channel filters
2. `text-embedding-3-small` embeds the query
3. Pinecone query with metadata filter (section_type, persona, channel, message_house_id, priority)
4. Top-K results reranked by score
5. Session context updated (active house, used chunks)

**Fallback:** If Pinecone is unavailable, keyword scoring across SQLite store.

**Session tracking:** Single session state per server instance — active house, used chunks, confidence level, persona context.

### 4.4 Artifact Generation

Two modes:

**Mode A — Skill Templates** (`generator.py`)
- 7 pre-built skill templates stored as JSON in `data/skills/`
- Each skill has a `prompt_template` and `sections` definition
- Generator builds context from the active house (top messages, personas, positioning)
- GPT-4o-mini fills the template (temperature 0.7)
- Output: `GeneratedArtifact` with raw LLM content + parsed sections dict

**Mode B — Direct Generation** (`web_app.py`)
- Per-section LLM generation for filling missing framework sections
- Fixed prompts per section type (summary, tagline, positioning, differentiation, etc.)
- Used by the "Generate with AI" buttons in the upload flow

### 4.5 Visual Artifacts

Three artifact types rendered as standalone HTML pages:

| Type | URL | Contents |
|---|---|---|
| `one_pager` | `/artifact/one_pager/{house_id}` | Dark hero + positioning card + color-coded message grid + persona cards |
| `social_posts` | `/artifact/social_posts/{house_id}` | LinkedIn, Twitter, email post cards with channel tags |
| `email_template` | `/artifact/email_template/{house_id}` | Awareness + consideration + decision email stages |

Custom CSS design system (no external JS frameworks) with CSS variables, Inter font, dark gradient hero, color-coded section blocks.

### 4.6 MCP Server Interface

15+ tools exposed via FastMCP (SSE transport) for use by AI assistants:

**Category: Grounding** — `search_messaging`, `set_active_house`, `get_message_house`, `list_message_houses`, `compare_houses`, `get_grounding_context`, `reset_conversation`

**Category: Artifacts** — `generate_artifact`, `generate_one_pager`, `generate_social_posts`, `generate_email_template`, `build_ui_artifact`, `list_skills`

**Category: Admin** — `check_framework_completeness`, `get_framework_spec`, `seed_database`

### 4.7 Admin UI

Single-page application served at `/`. No build step required (vanilla JS + inline CSS).

**Sections:**
- Dashboard (stats card)
- Frameworks (list + full framework editor with tabs: Overview, Key Messages, Personas, Markdown)
- Artifact Generator (framework selector, skill selector, output + visual link)
- Upload Source (drag-drop → auto-extract → completeness display + KYM card + missing sections)
- Skills (search, create, edit, delete skill templates)
- Seed (load sample data)

---

## Planned Architecture — v0.7: Hybrid RAG + Knowledge Graph

> **Status: Not yet implemented.** This section describes the target architecture for the v0.7 milestone.

The core design goal is a strict separation between two retrieval modes:

- **Vector search (Pinecone)** — semantic similarity for exploratory queries. Finds thematically relevant messaging. Results are approximate by design.
- **Graph traversal (Knowledge Graph)** — deterministic retrieval via typed relationships. Used when an AI agent needs verbatim approved content: an exact tagline, a locked proof point, a specific persona's buying triggers. Returns exact matches, not nearest neighbors.

Together they eliminate the failure mode where an LLM grounds against a *similar but not approved* message because vector search returned a close-but-wrong result.

### Knowledge Graph Schema

The graph uses generic node types — `GroundingDocument` and `GroundingChunk` — rather than `MessageHouse`/`KeyMessage`. This makes the graph layer content-type-agnostic: a brand guide, competitive brief, or corp narrative uses the same graph schema as a message house.

| Node / Entity | Attributes | Description |
|---|---|---|
| GroundingDocument | id, name, document_type, summary | Any structured grounding document (message house, brand guide, competitive brief, corp narrative, persona library). |
| GroundingChunk | id, content, section_type, priority | Individual content unit from a document — maps to `KeyMessage` for message houses, `style_rule` for brand guides, etc. |
| Persona | id, name, pain_points, buying_triggers | Target buyer or user roles with explicit behavioral triggers. |
| Channel | id, name, constraints | Content requirements per delivery channel. |

### Graph Relationships

The property graph maintains the following explicit relationships:

- `(GroundingDocument) -[:CONTAINS]-> (GroundingChunk)`
- `(GroundingDocument) -[:TARGETS]-> (Persona)`
- `(GroundingChunk) -[:APPLIES_TO]-> (Channel)`
- `(GroundingChunk) -[:ADDRESSES]-> (Persona)`

### Hybrid Indexing Strategy

| Search Type | Use Case | Storage |
|---|---|---|
| Vector (Pinecone) | Broad thematic search, semantic similarity | Embeddings of message content + house fields |
| Graph (SQLite adjacency tables) | Explicit relationship queries, path traversal | Entity + relationship store — Neo4j migration path for scale |
| Keyword (SQLite) | Exact match, structured filtering | Full-text search on message content |

The system routes queries by `retrieval_mode` parameter:
- `vector` — Pinecone semantic search only
- `graph` — Graph traversal for explicit relationships (governance/verbatim content)
- `hybrid` — Vector first, graph traversal for related context (default)
- `keyword` — SQLite full-text fallback

### Multi-Content-Type Data Model

The `message_houses` table stores all grounding document types via a `document_type` discriminator. This avoids schema proliferation as new document types are added.

| DocumentType | Purpose | Key SectionType Variants |
|---|---|---|
| `message_house` | Brand messaging frameworks (current default) | headline, subhead, benefit, proof_point, objection, social_proof, positioning, use_case, know_your_market |
| `brand_guide` | Brand voice, style guidelines, word lists | brand_voice, style_rule, word_list |
| `competitive_brief` | Competitor analysis and response strategies | competitor_strength, competitor_weakness, competitive_response |
| `corp_narrative` | Company story, values, founding narrative | narrative_pillar, company_value, founding_story |
| `persona_library` | Standalone buyer/user persona definitions | persona_detail |

**Channel as a first-class entity:** `Channel` is promoted from a code enum to a `ChannelModel` database table. Seeded defaults: `all`, `email`, `linkedin`, `twitter`, `paid_ads`, `landing_page`, `sales_deck`. Users can define custom channels (e.g., `partner_portal`, `in-app`) without code changes.

### Enhanced Multimodal Document Processing Pipeline

The intake pipeline will be extended to handle complex document formats and visual content:

**Multimodal Fallback:** When a page contains a high ratio of graphical elements or complex layouts, the pipeline will route it to a vision model (GPT-4V) for layout meaning extraction — handling diagrams and infographic-heavy slides that basic PDF parsers miss.

**Structural Table Extraction:** Preserves row and column relationships when extracting tables, maintaining header semantics for queryable structured data. _(Partially implemented in v0.6 for DOCX — PDF and vision-based table extraction is planned.)_

**Unified Hybrid Indexing:** On ingest, text chunks are embedded and routed to Pinecone while entity relationships (House→Message→Persona→Channel) are simultaneously written to the graph store.

---

## 5. Integration Points

### MCP Client (Claude, Cursor, etc.)
- Transport: SSE at `/mcp`
- Auth: None (localhost/tunnel only in v0.1)
- Agent prompt: `AGENT_PROMPT.md` (paste into system prompt or custom instructions)

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
  → extract_text()          [pypdf / python-docx]
  → structurer.structure()  [GPT-4o-mini]
  → store.upsert_house()    [SQLite]
  → engine.index_house()    [Pinecone + OpenAI embeddings]

MCP search_messaging(query)
  → _embed(query)            [OpenAI]
  → index.query(...)         [Pinecone]
  → _rerank(matches)
  → GroundingResponse

MCP generate_artifact(skill_id)
  → skill.fill_prompt()      [JSON template + house context]
  → GPT-4o-mini              [generation]
  → GeneratedArtifact

GET /artifact/{type}/{house_id}
  → store.get_house()
  → _render_one_pager() / _render_social_posts() / _render_email_template()
  → standalone HTML page
```

---

## 7. Tech Stack

| Layer | Technology |
|---|---|
| MCP Server | FastMCP 3.x (SSE transport) |
| Web API | FastAPI 0.100+ |
| ASGI Server | Uvicorn |
| ORM / DB | SQLAlchemy 2.0 + SQLite |
| Data Validation | Pydantic 2.0 |
| LLM | OpenAI API (GPT-4o-mini) |
| Embeddings | OpenAI text-embedding-3-small |
| Vector DB | Pinecone serverless |
| PDF extraction | pypdf |
| DOCX extraction | python-docx |
| Frontend | Vanilla JS + inline CSS (no build step) |
| Python | 3.11+ |

---

## 8. Non-Goals (v0.1)

These are explicitly out of scope for the current version:

- **Authentication / Authorization** — All endpoints are open. Intended for local or tunneled use.
- **Multi-tenancy** — Single user/org per instance.
- **Real-time collaboration** — No comments, approvals, or change tracking.
- **Custom embedding models** — Only `text-embedding-3-small` supported.
- **Non-OpenAI LLMs** — Structuring and generation use OpenAI only.
- **Framework versioning** — No snapshot or diff capability.
- **Analytics** — No usage tracking, artifact effectiveness scoring, or framework adoption metrics.
- **Webhook/event system** — No notifications or external triggers on framework changes.

---

## 9. Constraints

- Pinecone is optional — system degrades gracefully to keyword search
- Document text is truncated at 24,000 chars before LLM structuring (GPT-4o-mini context limit management)
- Artifact HTML is stateless — generated fresh from the SQLite store on each request
- Session state is in-memory — lost on server restart
- Single SQLite file (`msgstack.db`) — not suitable for concurrent write-heavy load

---

## 10. Quality Criteria

A generated artifact is considered "grounded" if:
- At least 3 key messages cited from the active framework
- Confidence score > 0.5 from vector search
- No invented statistics or proof points (only pull from framework)

A Message House is considered "complete" if:
- All required fields populated (summary, audience, positioning, tagline, differentiation)
- Minimum 2 headlines, 3 benefits, 2 proof points, 1 objection
- At least 1 persona
- Completeness score ≥ 80
