# MsgStack

<img width="1535" height="1024" alt="image" src="https://github.com/user-attachments/assets/2d3ffa32-9906-4efe-b0ad-ca621fc83fce" />


[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-violet.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![FastMCP](https://img.shields.io/badge/MCP-FastMCP-blueviolet)](https://github.com/jlowin/fastmcp)
[![GitHub Stars](https://img.shields.io/github/stars/abidc/msgstack-mcp?style=social)](https://github.com/abidc/msgstack-mcp)

**The messaging governance layer for AI-powered marketing teams.**

> Your AI agents are freelancing your brand. MsgStack gives them a rulebook.

MsgStack is an open source MCP server + admin UI that turns your brand messaging documents into a structured knowledge graph. Every AI tool on your team — Claude, Cursor, ChatGPT, or your own agents — can query it before generating content, ensuring what comes out is anchored in approved positioning.

---

## Why MsgStack?

When marketing teams adopt AI for content generation, a new problem emerges: **the AI doesn't know what your brand is actually approved to say.**

- An SDR asks Claude to write a cold email. Claude doesn't know your positioning, so it freelances.
- A regional team uses ChatGPT to localize a one-pager. The output contradicts your core differentiators.
- A new hire prompts Copilot to draft a LinkedIn post. It makes up a proof point.

MsgStack fixes this by making your messaging frameworks **machine-readable and directly queryable** via the [Model Context Protocol](https://modelcontextprotocol.io/). Before any AI generates content, it searches your approved message house for the right headlines, proof points, personas, and positioning — and uses those verbatim.

---

## What it does

```
Your Source Document (PDF / DOCX / Google Drive)
         ↓  extract → LLM structure
MessageHouse  (positioning · tagline · personas · key messages · pillars)
         ↓  embed → Turbovec  +  build → Knowledge Graph
    ┌─────────────────────────────────────────┐
    │  Semantic Search   │  Graph Traversal   │
    │  (vector approx.)  │  (verbatim exact)  │
    └────────────────────┴────────────────────┘
         ↓  skill template + grounding context + LLM
Grounded Artifact  (one-pager · email · battlecard · LinkedIn · blog · …)
```

**Two retrieval modes — neither approximates approved content:**
- **Vector (Turbovec):** local semantic similarity for exploratory queries — finds thematically relevant messaging (in-process, <0.1ms database latency)
- **Graph (NetworkX):** deterministic traversal for verbatim approved content — returns exact taglines, locked proof points, specific buying triggers — never approximated

---

## Quick Start

### Option A — Docker (recommended)

```bash
git clone https://github.com/abidc/msgstack-mcp.git
cd msgstack-mcp
cp .env.example .env
# Add OPENAI_API_KEY to .env (required)

docker compose up -d
```

→ Admin UI: `http://localhost:8001/`  
→ MCP endpoint: `http://localhost:8001/mcp`

### Option B — Python

```bash
git clone https://github.com/abidc/msgstack-mcp.git
cd msgstack-mcp
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Add your API keys

python run_server.py
```

**Load sample data to explore:**
```bash
python -c "from seed_data.seed import seed; seed()"
```

---

## Connect to your AI client

### Claude Desktop
Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
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

### Claude Code (CLI)
```bash
claude mcp add msgstack --transport sse http://localhost:8001/mcp
```

### Cursor / OpenWebUI / any MCP client
Point the MCP server URL to `http://localhost:8001/mcp` (SSE transport).

Once connected, your AI assistant will discover all available tools automatically via `system_instructions` and `quick_start` prompts.

---

## MCP Tools

Connect any MCP-compatible AI and it gains access to:

| Tool | What it does |
|------|-------------|
| `list_message_houses` | List all frameworks — always call first when a brand is mentioned |
| `search_messaging` | Semantic + keyword search across approved messaging |
| `get_graph_connections` | Deterministic graph traversal — verbatim approved content |
| `set_active_house` | Pin a framework for the session |
| `get_message_house` | Retrieve full framework for research |
| `generate_artifact` | Generate a grounded artifact (one-pager, email, battlecard, …) |
| `build_ui_artifact` | Get a visual HTML page URL for an artifact |
| `list_skills` | List available artifact types with required context |
| `check_framework_completeness` | Score a framework against the spec (0–100) + recommendations |
| `compare_houses` | Side-by-side comparison of two frameworks |
| `get_grounding_context` | Current session: active house, used chunks, confidence |
| `reset_conversation` | Clear session state |
| `get_framework_spec` | Full specification for a complete messaging framework |
| `list_channels` | All messaging channels including custom ones |

### Artifact types (`skill_id`)

| Skill | Required context |
|-------|----------------|
| `one_pager` | — |
| `email_template` | `stage`: awareness \| consideration \| decision |
| `linkedin_post` | — |
| `battlecard` | `competitor`: competitor name |
| `press_release` | `announcement`: announcement summary |
| `blog_post` | `topic`: blog topic |
| `social_posts` | — |
| `talk_track` | — |
| `objection_handler` | — |
| `executive_summary` | — |
| `partner_brief` | — |
| `event_brief` | `event_name`: event name |

---

## Admin UI

Navigate to `http://localhost:8001/` for the web interface:

| Section | What you can do |
|---------|----------------|
| **Dashboard** | Stats: frameworks, messages, personas; graph health widget |
| **Frameworks** | Browse, create, edit, delete message houses; tabbed detail (Overview / Messages / Personas) |
| **Artifacts** | Select framework + skill, generate, preview structured output, open visual page |
| **Upload** | Drop PDF / DOCX / TXT → auto-extract and structure via LLM; preview before saving |
| **Skills** | Create, edit, delete artifact skill templates |
| **Graph Explorer** | Interactive Cytoscape.js visualization — filter by node type, click for details |
| **Settings** | API keys, workspaces, theme |

---

## Architecture

```
run_server.py            # PathRouter: /mcp → FastMCP, /* → FastAPI
├── src/server.py        # FastMCP — 17 MCP tools + 2 prompts
├── src/web_app.py       # FastAPI admin UI — CRUD, upload, artifact endpoints
├── src/web/
│   ├── base.html        # Jinja2 base (sidebar, nav, dark theme)
│   └── dashboard.html   # Admin SPA — all sections + Graph Explorer
│
├── src/models.py        # Pydantic: MessageHouse, KeyMessage, Persona, Pillar, …
├── src/store.py         # SQLAlchemy ORM → SQLite (default) / PostgreSQL
│
├── src/pipeline/
│   ├── extract.py       # PDF / DOCX / TXT → high-fidelity Markdown text (pypdf, python-docx); 10MB guard
│   ├── structure.py     # Text → StructuredHouse via GPT-4o-mini
│   ├── generator.py     # Skill template + full grounding context → artifact
│   └── skills.py        # JSON skill file manager (12 built-in templates)
│
├── src/grounding/
│   ├── search.py        # Turbovec local vector search + SQLite pre-filtering + source_markdown indexing
│   ├── graph.py         # NetworkX DiGraph — deterministic retrieval
│   ├── session.py       # In-memory session (active house, used chunks, 30-min TTL)
│   └── tools.py         # Grounding tool implementations
│
├── data/sources/        # Auto-generated raw Markdown proxy files (one per house)
└── seed_data/seed.py    # Sample message houses for development
```

**Single server, two interfaces:**
- `POST /mcp` → FastMCP SSE transport (Claude, Cursor, any MCP client)
- `GET/POST /api/*` → FastAPI admin REST endpoints
- `GET /` → Admin single-page UI
- `GET /artifact/{type}/{house_id}` → Standalone visual artifact pages

---

## Data Model

### MessageHouse
The core entity — a structured representation of a product's approved messaging.

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Framework name |
| `document_type` | enum | `message_house` / `brand_guide` / `competitive_brief` / `corp_narrative` / `persona_library` |
| `positioning` | str | Core positioning statement |
| `tagline` | str | Punchy tagline (≤7 words) |
| `differentiation` | str | Key differentiators |
| `audience` | str | Target buyer + user roles |
| `brand_personality` | str | Tone, voice, style |
| `summary` | str | 2–3 sentence product overview |
| `status` | enum | `active` / `archived` / `needs_review` |

### KeyMessage
Individual approved message units, linked to a house.

| Field | Type | Description |
|-------|------|-------------|
| `section_type` | enum | `headline` / `subhead` / `benefit` / `use_case` / `proof_point` / `objection` / `social_proof` / `positioning` |
| `priority` | int 1–5 | 1 = highest priority |
| `content` | str | The approved message copy |
| `variants` | dict | Channel rewrites: `{linkedin: "...", email: "..."}` |
| `personas` | list[str] | Which personas this applies to |
| `channels` | list[enum] | `all` / `linkedin` / `email` / `landing` / `paid` / `twitter` / `blog` |

### Knowledge Graph Schema
```
MessageHouse
  ├─[HAS_SECTION]──► Section ──[CONTAINS]──► KeyMessage
  │                                             ├─[ADDRESSES]──► Persona
  │                                             └─[APPLIES_TO]─► Channel
  ├─[HAS_PILLAR]───► MessagingPillar ──[GROUPS]──► KeyMessage
  └─[TARGETS]──────► Persona
                       ├─[HAS_PAIN_POINT]──► PainPoint
                       ├─[HAS_TRIGGER]─────► BuyingTrigger
                       └─[HAS_OBJECTION]───► Objection
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | **Yes** | — | LLM structuring, generation, embeddings |
| `TURBOVEC_INDEX_PATH` | No | `data/msgstack_vectors.tvim` | Path to store the local Turbovec vector index |
| `MSGSTACK_BASE_URL` | No | `http://localhost:8001` | Base URL for artifact links returned by MCP tools |
| `DATABASE_URL` | No | `sqlite:///msgstack.db` | SQLAlchemy URL — use `postgresql://...` for production |
| `MSGSTACK_AUTH_ENABLED` | No | `false` | Enable API key auth on admin endpoints |
| `MSGSTACK_SOURCES_DIR` | No | `data/sources` | Directory where raw Markdown proxy files are saved |
| `LOG_FORMAT` | No | `text` | `text` or `json` |

---

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt

# Seed sample data
python -c "from seed_data.seed import seed; seed()"

# Start combined server
python run_server.py

# Run tests
pytest tests/

# Lint
ruff check src/
```

### Re-indexing vectors
```bash
# Single house
curl -X POST http://localhost:8001/api/houses/{house_id}/index

# All houses
curl -X POST http://localhost:8001/api/index-all
```

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full versioned roadmap.

**Current version: v0.8.2**

**Recent shipped:**
- `v0.8.1` — Turbovec local vector search replacing Pinecone (zero external vector DB dependency)
- `v0.8.2` — Automatic Markdown Translation Layer: high-fidelity DOCX/PDF proxy files persisted and indexed under `source_markdown` section type for full-content RAG retrieval

**Coming next:**
- `v0.8.x` — Visual Artifact Engine (Fabric.js canvas, reveal.js presentations, Penpot export)
- `v0.9` — Governance & Alignment Engine (score any content against the message house)
- `v1.0` — Competitive Intelligence (import competitor docs, auto-sharpen battlecards)

Community-suggested items: open an issue with the `enhancement` label.

---

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

Areas where community help is most useful right now:
- **Source connectors** — Notion, Confluence, Box (see v1.3 roadmap)
- **Additional MCP clients** — testing with OpenWebUI, Zed, LibreChat
- **Skill templates** — new artifact types in `data/skills/`
- **Bug reports** — especially around document extraction edge cases

---

## License

[Apache 2.0](LICENSE) — free to use, self-host, modify, and distribute.

---

## Links

- 🌐 Website: [msgstack.ai](https://www.msgstack.ai)
- 📖 Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 🗺️ Roadmap: [ROADMAP.md](ROADMAP.md)
- 💬 Discussions: [GitHub Discussions](https://github.com/abidc/msgstack-mcp/discussions)
