# MsgStack MCP

MCP server + admin UI for marketing messaging grounding and dynamic asset generation via Prefab.

**What it does:**
- Upload source documents (PDF, DOCX, TXT) → extract → LLM structurer → structured MessageHouse
- Manage messaging frameworks with key messages and personas
- MCP tools for AI grounding (Claude, ChatGPT, Cursor)
- Skill file system for artifact generation templates
- Prefab-powered artifact previews

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env  # add your OPENAI_API_KEY

# Start admin UI
python -m src.web_app

# Open http://localhost:8000
```

## Architecture

```
src/
├── models.py           # Pydantic data models
├── store.py           # SQLite-backed storage
├── server.py           # FastMCP server (MCP tools)
├── web_app.py         # FastAPI admin UI
├── web/index.html     # Single-page admin UI
├── pipeline/
│   ├── extract.py     # PDF/DOCX/TXT extraction
│   ├── structure.py   # LLM structurer → MessageHouse
│   └── skills.py      # Skill file manager
└── grounding/
    ├── search.py      # Hybrid Pinecone search
    └── session.py     # Session tracking
```

## MCP Tools

### Grounding
- `search_messaging` — Semantic + metadata search across frameworks
- `set_active_house` — Pin a framework for the session
- `get_message_house` — Full retrieval with key messages + personas
- `list_message_houses` — Available frameworks

### Artifacts
- `generate_one_pager` — Prefab UI one-pager
- `generate_social_posts` — Channel-specific copy
- `generate_email_template` — Funnel-stage emails

## Admin UI Features

- **Dashboard** — Stats and recent frameworks
- **Frameworks** — CRUD for messaging houses, key messages, personas
- **Upload** — Drag-drop source files → auto-extract to MessageHouse
- **Skills** — Manage artifact generation prompt templates

## Environment Variables

```env
OPENAI_API_KEY=       # Required for structurer
PINECONE_API_KEY=    # Optional — for vector search
```

## Developing

```bash
# Seed sample data
python -c "from seed_data.seed import seed; seed()"

# Run admin UI
python -m src.web_app

# Run MCP server (for AI tool connection)
python -m src.server
```
