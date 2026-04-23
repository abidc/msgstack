# MsgStack MCP

MCP server for marketing messaging grounding and dynamic asset generation via Prefab.

Give any AI content tool (Claude, ChatGPT, Cursor) access to your brand's messaging frameworks and the ability to generate on-brand marketing artifacts — in-chat, via Prefab UI.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env  # add your OPENAI_API_KEY and PINECONE_API_KEY
```

```bash
# Seed the database with sample data
python -c "from seed_data.seed import seed; seed()"

# Run the MCP server
python -m src.server
```

## MCP Tools

### Grounding
- `search_messaging` — Semantic + metadata search across messaging frameworks
- `set_active_house` — Pin a messaging framework for the session
- `get_message_house` — Full retrieval of a message house with all key messages and personas
- `list_message_houses` — Discover available messaging frameworks
- `compare_houses` — Side-by-side comparison of two or more houses
- `get_grounding_context` — Current session grounding state
- `reset_conversation` — Clear session context

### Artifact Generation (Prefab)
- `generate_one_pager` — Messaging one-pager as an interactive Prefab UI
- `generate_social_posts` — Channel-specific social copy grounded in messaging
- `generate_email_template` — Funnel-stage email templates with subject/body/CTA

## Architecture

```
src/
├── models.py          # Pydantic data models
├── store.py           # SQLite-backed message house storage
├── server.py          # FastMCP server entry point
├── grounding/
│   ├── search.py      # Hybrid vector + metadata search with Pinecone
│   ├── session.py     # In-memory session tracking
│   └── tools.py       # MCP tool implementations
├── artifacts/
│   └── generators.py  # Prefab component trees
├── pipeline/          # Content sync pipeline (Google Drive, Notion, OneDrive)
└── sources/           # Source connectors
```

## Environment Variables

```env
OPENAI_API_KEY=       # For embeddings
PINECONE_API_KEY=     # For vector search
PINECONE_INDEX=msgstack-chunks  # defaults to this
```

## Developing

```bash
# Preview Prefab apps locally
fastmcp dev apps src/server.py

# Run tests
pytest tests/
```