# MsgStack MCP

**Marketing messaging infrastructure for AI assistants.**

MsgStack is an MCP server + admin UI that manages structured marketing "Message Houses" — single sources of truth for positioning, key messages, personas, and proof points. AI assistants use these frameworks to ground generated content in approved messaging, and marketing teams use the admin UI to build, upload, and manage them.

---

## What It Does

```
Source Document (PDF/DOCX/TXT)
        ↓  [extract + LLM structure]
MessageHouse (positioning, tagline, messages, personas)
        ↓  [embed → Pinecone]
Semantic Search ← AI assistant queries for relevant content
        ↓  [skill template + LLM]
Grounded Artifact (one-pager, email, LinkedIn post, battlecard...)
```

**For AI assistants (via MCP):**
- Search approved messaging by section type, persona, and channel
- Set an active framework for the session and track what's been used
- Generate on-brand artifacts grounded in the active framework
- Get shareable visual artifact URLs

**For marketing teams (via admin UI at `/`):**
- Upload source documents → auto-extract to structured framework via LLM
- Manage messaging frameworks, key messages, personas, and skills
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
├── src/server.py        # FastMCP server — 15+ MCP tools
├── src/web_app.py       # FastAPI admin UI — CRUD, upload, artifact endpoints
├── src/web/index.html   # Single-page admin UI
│
├── src/models.py        # Pydantic: MessageHouse, KeyMessage, Persona, etc.
├── src/store.py         # SQLAlchemy ORM → SQLite (msgstack.db)
│
├── src/pipeline/
│   ├── extract.py       # PDF/DOCX/TXT → raw text (pypdf, python-docx)
│   ├── structure.py     # Raw text → StructuredHouse via GPT-4o-mini
│   ├── generator.py     # Skill template + house context → artifact via LLM
│   └── skills.py        # JSON skill file manager (7 built-in templates)
│
├── src/grounding/
│   ├── search.py        # Pinecone hybrid vector + metadata search
│   ├── session.py       # In-memory session state (active house, used chunks)
│   └── tools.py         # Grounding tool implementations
│
├── src/artifacts/       # Prefab UI artifact builders (optional visual layer)
└── seed_data/seed.py    # 10 sample message houses for development
```

**Single server, two interfaces:**
- `GET/POST /api/*` → FastAPI admin REST endpoints
- `POST /mcp` → FastMCP SSE transport (for Claude, Cursor, etc.)
- `GET /artifact/{type}/{house_id}` → Standalone HTML artifact pages
- `GET /` → Admin single-page UI

---

## Data Model

### MessageHouse
The core entity. A structured representation of a product's approved messaging.

| Field | Type | Description |
|---|---|---|
| `name` | str | Framework name |
| `summary` | str | 2-3 sentence product overview |
| `audience` | str | Target buyer + user roles |
| `brand_personality` | str | Tone, voice, word choices |
| `positioning` | str | Core positioning statement |
| `tagline` | str | Punchy tagline (≤7 words) |
| `differentiation` | str | Key differentiators vs competitors |
| `status` | enum | active / archived / needs_review |
| `source` | str | manual / upload / seed |

### KeyMessage
Individual message units, linked to a house.

| Field | Type | Description |
|---|---|---|
| `section_type` | enum | headline / subhead / benefit / use_case / proof_point / objection / social_proof / positioning |
| `priority` | int 1-5 | 1 = most important |
| `content` | str | Message copy |
| `variants` | dict | Channel-specific rewrites `{linkedin: "...", email: "..."}` |
| `personas` | list[str] | Which personas this message applies to |
| `channels` | list[enum] | all / linkedin / email / landing / paid / twitter / blog |

### Persona
Buyer personas linked to a house.

| Field | Type | Description |
|---|---|---|
| `name` | str | Persona name (e.g., "VP Engineering") |
| `description` | str | Role description |
| `pain_points` | list[str] | Core frustrations |
| `buying_triggers` | list[str] | What makes them buy |
| `objections` | list[str] | What stops them |

---

## MCP Tools Reference

Connect Claude (or any MCP-compatible AI) to `http://localhost:8001/mcp` (SSE transport).

### Grounding Tools

#### `search_messaging(query, section_types?, personas?, channels?, message_houses?, min_priority?)`
Semantic + metadata search across all indexed frameworks. Returns grounded results with confidence scores.
- `section_types`: filter by `["headline", "benefit", "proof_point", "use_case", ...]`
- `personas`: filter by persona name substring
- `channels`: filter by `["linkedin", "email", "paid", ...]`
- `min_priority`: only return messages with priority ≤ this value (1 = highest)

#### `set_active_house(house_id?, house_name?)`
Pin a framework for the session. Subsequent searches automatically scope to this house.

#### `get_message_house(house_id?, house_name?, include?)`
Retrieve a complete framework. `include` can be `["key_messages", "personas", "markdown"]`.

#### `list_message_houses(query?)`
List all available frameworks. Optionally filter by name substring.

#### `compare_houses(house_ids)`
Side-by-side comparison of two or more frameworks (positioning, taglines, differentiation).

#### `get_grounding_context()`
Return current session state: active house, used chunks, confidence level.

#### `reset_conversation()`
Clear session state and start fresh.

### Artifact Tools

#### `generate_artifact(skill_id, house_id?, custom_context?)`
Generate a marketing artifact using a skill template grounded in the active house.

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

`custom_context` examples: `{"stage": "decision", "competitor": "Workday", "topic": "ROI"}`

#### `build_ui_artifact(artifact_type, house_id?)`
Returns a public URL for a visual standalone artifact page.
- `artifact_type`: `one_pager` / `social_posts` / `email_template`
- URL format: `{MSGSTACK_BASE_URL}/artifact/{type}/{house_id}`

#### `generate_one_pager(house_id?)`, `generate_social_posts(house_id?)`, `generate_email_template(house_id?)`
Shorthand artifact generators for the three visual artifact types.

#### `list_skills()`
List all available skill templates with their sections and metadata.

### Admin Tools

#### `check_framework_completeness(house_id?)`
Score a framework against the spec (0-100). Checks: positioning length, tagline length, message counts per section type, persona coverage, channel variants.

#### `get_framework_spec()`
Return the complete framework specification with all required fields and counts.

#### `seed_database()`
Load the 10 built-in sample message houses into the database.

---

## Admin UI

Navigate to `http://localhost:8001/` for the web interface.

| Section | What you can do |
|---|---|
| **Dashboard** | Stats: house count, message count, persona count, skills count |
| **Frameworks** | Browse, search, create, edit, delete message houses; view all messages and personas per house; export markdown |
| **Artifact Generator** | Select a framework + skill, generate, preview structured output, open visual page |
| **Upload Source** | Drop a PDF/DOCX/TXT → auto-extracts and structures into a new framework via LLM |
| **Skills** | Create, edit, delete artifact skill templates; search skills |
| **Seed** | Load sample data |

### Upload Flow
1. Drop or select a file in the Upload Source section
2. Text is extracted immediately (fast — no LLM)
3. LLM structuring runs automatically — maps document sections to MessageHouse fields
4. Framework is saved to SQLite and indexed to Pinecone
5. Know Your Market pre-section (if present) is displayed separately
6. Missing sections are flagged with "Generate with AI" fill-in buttons

---

## Document Structuring

The LLM structurer (`structure.py`) is trained to recognize a wide variety of source document formats, not just the canonical MessageHouse format:

| Source Document Section | Maps To |
|---|---|
| Know Your Market / Know Your Customer | `know_your_market` (pre-section) + extracts audience, positioning, differentiation |
| Umbrella Message Headline | `tagline` + `headline` key message |
| Top 3 Value Pillars | `benefit` key messages (one per pillar, with proof point inline) |
| What It Does / Elevator Pitch / One-Paragraph Description | `summary` |
| Key Use Cases / Top Use Cases table | `use_case` key messages |
| Customer Proof Points table | `proof_point` key messages |
| FOMO / Competition sections | `objection` key messages |
| Personas / Audience | `Persona` records |

Missing sections are flagged and can be filled via AI generation.

---

## Pinecone Integration

If `PINECONE_API_KEY` is set, `index_house()` embeds and upserts the following per framework:
- All `KeyMessage` records (one vector each)
- `summary`, `audience`, `positioning`, `differentiation`, `tagline` fields (one vector each)
- `know_your_market` block from the saved markdown

**Index config:** `msgstack-chunks`, serverless (AWS us-east-1), dimension 1536, cosine metric, `text-embedding-3-small`.

If Pinecone is not configured, search falls back to keyword scoring across the SQLite store.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | Used by structurer, generator, and embedding |
| `PINECONE_API_KEY` | No | — | Vector search; falls back to keyword search if absent |
| `PINECONE_INDEX` | No | `msgstack-chunks` | Pinecone index name |
| `MSGSTACK_BASE_URL` | No | `http://localhost:8001` | Base URL used in artifact links returned by MCP tools |

---

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt

# Seed sample data (10 built-in message houses)
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

Version `0.1.0` — active development. Core pipeline and MCP tools are functional. See [ROADMAP.md](ROADMAP.md) for planned work.
