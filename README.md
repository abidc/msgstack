# MsgStack MCP

**Marketing messaging infrastructure for AI assistants.**

MsgStack is an MCP server + admin UI that manages structured marketing "Message Houses" — single sources of truth for positioning, key messages, personas, and proof points. AI assistants use these frameworks to ground generated content in approved messaging, and marketing teams use the admin UI to build, upload, and manage them.

---

## What It Does

```
Source Document (PDF/DOCX/TXT)
        ↓  [extract + LLM structure]
MessageHouse (positioning, tagline, messages, personas, pillars)
        ↓  [embed → Pinecone]  +  [build → Knowledge Graph]
Semantic Search ← AI assistant queries for relevant content
Deterministic Graph ← AI assistant queries for verbatim approved content
        ↓  [skill template + full grounding context + LLM]
Grounded Artifact (one-pager, email, LinkedIn post, battlecard...)
```

**For AI assistants (via MCP):**
- Search approved messaging by section type, persona, and channel
- Retrieve verbatim approved content via deterministic graph traversal (bypasses vector approximation)
- Set an active framework for the session and track what's been used
- Generate on-brand artifacts grounded in ALL key messages and ALL persona attributes
- Get shareable visual artifact URLs

**For marketing teams (via admin UI at `/`):**
- Upload source documents → auto-extract to structured framework via LLM
- Manage messaging frameworks, key messages, personas, pillars, and skills
- Explore the knowledge graph interactively (Graph Explorer with Cytoscape.js)
- Preview generated artifacts as standalone HTML pages

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Add OPENAI_API_KEY (required), PINECONE_API_KEY (optional)

# 3. Start the server (MCP + admin UI on same port)
python run_server.py

# Admin UI:  http://localhost:8001/
# MCP SSE:   http://localhost:8001/mcp
# API docs:  http://localhost:8001/docs
```

**Optional: seed sample data**
```bash
python -c "from seed_data.seed import seed; seed()"
```

---

## Architecture

```
run_server.py            # PathRouter: /mcp → FastMCP, /* → FastAPI
├── src/server.py        # FastMCP server — 20+ MCP tools
├── src/web_app.py       # FastAPI admin UI — CRUD, upload, artifact endpoints
├── src/web/
│   ├── base.html        # Jinja2 base layout (sidebar, nav, theme toggle)
│   └── dashboard.html   # Admin SPA — all sections including Graph Explorer
│
├── src/models.py        # Pydantic: MessageHouse, KeyMessage, Persona, Pillar, etc.
├── src/store.py         # SQLAlchemy ORM → SQLite / PostgreSQL
│
├── src/pipeline/
│   ├── extract.py       # PDF/DOCX/TXT → raw text (pypdf, python-docx)
│   ├── structure.py     # Raw text → StructuredHouse via GPT-4o-mini
│   ├── generator.py     # Skill template + full house context → artifact via LLM
│   └── skills.py        # JSON skill file manager (12 built-in templates)
│
├── src/grounding/
│   ├── search.py        # Pinecone hybrid vector + metadata search
│   ├── graph.py         # Knowledge graph engine — deterministic retrieval via NetworkX
│   ├── session.py       # In-memory session state (active house, used chunks)
│   └── tools.py         # Grounding tool implementations
│
├── src/artifacts/       # Prefab UI artifact builders (optional visual layer)
└── seed_data/seed.py    # Sample message houses for development
```

**Single server, two interfaces:**
- `GET/POST /api/*` → FastAPI admin REST endpoints
- `POST /mcp` → FastMCP SSE transport (for Claude, Cursor, etc.)
- `GET /artifact/{type}/{house_id}` → Standalone HTML artifact pages
- `GET /` → Admin single-page UI (Jinja2 rendered)

---

## Data Model

### MessageHouse
The core entity. A structured representation of a product's approved messaging.

| Field | Type | Description |
|---|---|---|
| `name` | str | Framework name |
| `document_type` | enum | `message_house` / `brand_guide` / `competitive_brief` / `corp_narrative` / `persona_library` |
| `summary` | str | 2-3 sentence product overview |
| `audience` | str | Target buyer + user roles |
| `brand_personality` | str | Tone, voice, word choices |
| `positioning` | str | Core positioning statement |
| `tagline` | str | Punchy tagline (≤7 words) |
| `differentiation` | str | Key differentiators vs competitors |
| `status` | enum | active / archived / needs_review |
| `source` | str | manual / upload / google_drive / onedrive / seed |

### KeyMessage
Individual message units, linked to a house.

| Field | Type | Description |
|---|---|---|
| `section_type` | enum | headline / subhead / benefit / use_case / proof_point / objection / social_proof / positioning / know_your_market |
| `priority` | int 1-5 | 1 = most important |
| `content` | str | Message copy |
| `variants` | dict | Channel-specific rewrites `{linkedin: "...", email: "..."}` |
| `personas` | list[str] | Which personas this message applies to |
| `channels` | list[enum] | all / linkedin / email / landing / paid / twitter / blog |
| `pillar_id` | UUID | MessagingPillar this chunk belongs to (optional) |
| `pain_point_ids` | list[UUID] | PainPoints this message addresses |
| `objection_ids` | list[UUID] | Objections this message resolves |

### Persona
Buyer personas linked to a house.

| Field | Type | Description |
|---|---|---|
| `name` | str | Persona name (e.g., "VP Engineering") |
| `description` | str | Role description |
| `pain_points` | list[str] | Core frustrations |
| `buying_triggers` | list[str] | What makes them buy |
| `objections` | list[dict] | `{statement, response}` pairs |

### MessagingPillar
Strategic theme grouping key messages under a house.

| Field | Type | Description |
|---|---|---|
| `name` | str | Pillar name (e.g., "Speed & Reliability") |
| `description` | str | What this pillar represents |
| `house_id` | UUID | Parent framework |

### Knowledge Graph Nodes
The in-memory NetworkX graph (`graph.py`) promotes all entities to first-class typed nodes:

| Node Type | Edges |
|---|---|
| `GroundingDocument` | -[:CONTAINS]→ Pillar, Chunk; -[:TARGETS]→ Persona |
| `MessagingPillar` | -[:CONTAINS]→ GroundingChunk |
| `GroundingChunk` | -[:ADDRESSES]→ Persona; -[:APPLIES_TO]→ Channel; -[:ADDRESSES]→ PainPoint; -[:RESOLVES]→ Objection |
| `Persona` | -[:HAS_PAIN_POINT]→ PainPoint; -[:HAS_TRIGGER]→ BuyingTrigger; -[:HAS_OBJECTION]→ Objection |
| `Channel` | (target of APPLIES_TO) |
| `PainPoint` | (target of HAS_PAIN_POINT, ADDRESSES) |
| `BuyingTrigger` | (target of HAS_TRIGGER) |
| `Objection` | (target of HAS_OBJECTION, RESOLVES) |

---

## MCP Tools Reference

Connect Claude (or any MCP-compatible AI) to `http://localhost:8001/mcp` (SSE transport).

### Grounding Tools

#### `search_messaging(query, section_types?, personas?, channels?, message_houses?, retrieval_mode?, min_priority?)`
Semantic + metadata search across all indexed frameworks. Returns grounded results with confidence scores.
- `retrieval_mode`: `"hybrid"` (default), `"vector"`, `"graph"` (deterministic), `"keyword"`
- `section_types`: filter by `["headline", "benefit", "proof_point", "use_case", ...]`
- `personas`: filter by persona name substring
- `channels`: filter by `["linkedin", "email", "paid", ...]`
- `min_priority`: only return messages with priority ≤ this value (1 = highest)

#### `get_graph_connections(house_id, persona?, channel?)`
Deterministic graph traversal — returns verbatim approved content via typed relationships. Unlike `search_messaging`, this bypasses vector approximation entirely. Use when you need exact taglines, approved headlines, or locked proof points.

#### `set_active_house(house_id?, house_name?)`
Pin a framework for the session. Subsequent searches automatically scope to this house.

#### `get_message_house(house_id?, house_name?, include?)`
Retrieve a complete framework including all key messages and personas. `include` can be `["key_messages", "personas", "positioning"]` or `["all"]`.
**Note:** Use `generate_artifact` to generate content — do not write artifacts from this data directly.

#### `list_message_houses(query?)`
List all available frameworks with IDs and summaries. Response includes `_next_step` guidance on the correct next tool to call.

#### `compare_houses(house_ids)`
Side-by-side comparison of two or more frameworks (positioning, taglines, differentiation).

#### `get_grounding_context()`
Return current session state: active house, used chunks, confidence level.

#### `reset_conversation()`
Clear session state and start fresh.

#### `list_channels()`
List all available messaging channels including user-defined custom channels.

### Artifact Tools

#### `generate_artifact(skill_id, house_id?, house_name?, custom_context?)`
Generate a marketing artifact grounded in the complete message house. Loads ALL key messages (grouped by section type) and ALL personas with full attributes — no caps or truncation. A full structured grounding context is prepended to every prompt with an explicit "do not invent claims" contract.

Built-in `skill_id` values:
| Skill | Output |
|---|---|
| `one_pager` | Positioning overview with key messages, personas, proof points |
| `linkedin_post` | 150-300 word post with hook, body, CTA, hashtags |
| `email_template` | Funnel-stage email (awareness / consideration / decision) |
| `battlecard` | Competitive comparison with rebuttals |
| `press_release` | AP-style announcement with quotes and boilerplate |
| `blog_post` | Long-form SEO content with sections |
| `faq_document` | 8-12 Q&A pairs organized by theme |
| `talk_track` | Sales call script with discovery questions and objection handling |
| `objection_handler` | Full objection/rebuttal reference card |
| `event_brief` | Conference messaging brief with talking points and booth strategy |
| `executive_summary` | C-level SCR-format briefing |
| `partner_brief` | Channel partner messaging enablement sheet |

`custom_context` examples: `{"stage": "decision", "competitor": "Workday", "topic": "ROI", "event_name": "Dreamforce"}`

#### `build_ui_artifact(artifact_type, house_id?)`
Returns a public URL for a visual standalone artifact page (does NOT run the AI generator).
- `artifact_type`: `one_pager` / `social_posts` / `email_template`

#### `list_skills()`
List all available skill templates with their sections and metadata.

### Admin & Inspection Tools

#### `check_framework_completeness(house_id?)`
Score a framework against the spec (0-100). Checks: positioning length, tagline, message counts per section type, persona coverage, channel variants.

#### `get_framework_spec()`
Return the complete framework specification with all required fields and counts.

#### `list_mcp_tools()`
List all available MCP tools with descriptions. Use this to understand the full server capabilities.

#### `seed_database()`
Load the built-in sample message houses into the database.

### MCP Prompts

#### `system_instructions`
Complete operating guide for MsgStack tools — standard generation workflow, tool selection rules, required context per skill. Inject into your AI assistant's system prompt for correct tool routing.

#### `quick_start`
One-paragraph guide showing available frameworks and example generation requests.

---

## Admin UI

Navigate to `http://localhost:8001/` for the web interface (Jinja2-rendered, dark/light theme toggle).

| Section | What you can do |
|---|---|
| **Dashboard** | Stats: house count, message count, persona count, skills count; graph stats widget |
| **Frameworks** | Browse, search, create, edit, delete message houses; tabbed detail view (Overview / Messages / Personas); export markdown |
| **Artifacts** | Select a framework + skill, provide required context, generate, preview structured output, open visual page |
| **Upload** | Drop a PDF/DOCX/TXT → auto-extracts and structures into a new framework via LLM; preview before confirming |
| **Skills** | Create, edit, delete artifact skill templates |
| **Channels** | View and manage messaging channels |
| **Graph Explorer** | Interactive Cytoscape.js visualization of the full knowledge graph — filter by node type, click nodes for details, browse relationships |
| **Settings** | API keys, workspaces, token usage, theme |

### Upload Flow
1. Drop or select a file in the Upload section
2. Text is extracted immediately (no LLM)
3. LLM structuring runs automatically — maps document sections to MessageHouse fields
4. Preview the structured result; confirm or discard
5. Framework is saved to SQLite and indexed to Pinecone; graph is rebuilt
6. Missing sections are flagged with "Generate with AI" fill-in buttons

---

## Grounding Architecture

MsgStack uses a two-layer retrieval architecture:

**Vector layer (Pinecone)** — semantic similarity for exploratory queries. Finds thematically relevant messaging. Results are approximate by design. Used by `search_messaging` with `retrieval_mode="vector"` or `"hybrid"`.

**Graph layer (NetworkX)** — deterministic retrieval via typed relationships. Used when an AI agent needs verbatim approved content: exact taglines, locked proof points, specific persona buying triggers. Returns exact matches, not nearest neighbors. Used by `get_graph_connections` and `search_messaging` with `retrieval_mode="graph"`.

Together they eliminate the failure mode where an LLM grounds against a *similar but not approved* message.

---

## Document Structuring

The LLM structurer (`structure.py`) recognizes a wide variety of source document formats:

| Source Document Section | Maps To |
|---|---|
| Know Your Market / Know Your Customer | `know_your_market` (pre-section) + extracts audience, positioning, differentiation |
| Umbrella Message / Headline | `tagline` + `headline` key message |
| Top 3 Value Pillars | `benefit` key messages (one per pillar, with proof point inline) |
| What It Does / Elevator Pitch | `summary` |
| Key Use Cases table | `use_case` key messages |
| Customer Proof Points table | `proof_point` key messages |
| FOMO / Competition sections | `objection` key messages |
| Personas / Audience | `Persona` records with pain points, triggers, objections |

---

## Pinecone Integration

If `PINECONE_API_KEY` is set, `index_house()` embeds and upserts the following per framework:
- All `KeyMessage` records (one vector each)
- `summary`, `audience`, `positioning`, `differentiation`, `tagline` fields (one vector each)
- `know_your_market` block from the saved markdown

**Index config:** `msgstack-chunks`, serverless (AWS us-east-1), dimension 1536, cosine metric, `text-embedding-3-small`.

If Pinecone is not configured, search falls back to keyword scoring across the SQLite store. Graph traversal works regardless of Pinecone status.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | Used by structurer, generator, and embedding |
| `PINECONE_API_KEY` | No | — | Vector search; falls back to keyword search if absent |
| `PINECONE_INDEX` | No | `msgstack-chunks` | Pinecone index name |
| `MSGSTACK_BASE_URL` | No | `http://localhost:8001` | Base URL used in artifact links returned by MCP tools |
| `DATABASE_URL` | No | `sqlite:///msgstack.db` | SQLAlchemy URL; use `postgresql://...` for production |
| `MSGSTACK_AUTH_ENABLED` | No | `false` | Enable API key authentication |
| `LOG_FORMAT` | No | `text` | `text` or `json` |

---

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt

# Seed sample data
python -c "from seed_data.seed import seed; seed()"

# Start combined server (MCP + admin UI)
python run_server.py

# Run tests
pytest tests/

# Lint
ruff check src/
```

### Connecting to Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "msgstack": {
      "url": "http://localhost:8001/mcp",
      "transport": "sse"
    }
  }
}
```

### Connecting to Claude Code (CLI)
```bash
claude mcp add msgstack --transport sse http://localhost:8001/mcp
```

### Re-indexing a House to Pinecone
```bash
curl -X POST http://localhost:8001/api/houses/{house_id}/index
```

### Re-indexing All Houses
```bash
curl -X POST http://localhost:8001/api/index-all
```

---

## Project Status

Version `0.6` — active development. Knowledge graph engine implemented and live. See [ROADMAP.md](ROADMAP.md) for planned work including Google Drive and OneDrive/SharePoint source integrations (v0.8).
