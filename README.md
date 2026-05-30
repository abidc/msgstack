# MsgStack

<img width="1535" height="1024" alt="image" src="https://github.com/user-attachments/assets/2d3ffa32-9906-4efe-b0ad-ca621fc83fce" />


[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-violet.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![FastMCP](https://img.shields.io/badge/MCP-FastMCP-blueviolet)](https://github.com/jlowin/fastmcp)
[![GitHub Stars](https://img.shields.io/github/stars/abidc/msgstack-mcp?style=social)](https://github.com/abidc/msgstack-mcp)

**The organizational canon layer for AI grounding.**

> MsgStack is the canon layer for the organization. Departments own their domains of truth. AI tools and content workflows ground on that canon. When canon changes, downstream outputs stay aligned.

MsgStack is an open source MCP server + admin UI that turns your organization's authoritative, structured grounding content (the **"canon"**) into a structured knowledge graph. Every AI tool on your team — Claude, Cursor, ChatGPT, or your own agents — can query it before generating content, ensuring what comes out is anchored in approved truth. While MsgStack begins with product marketing as its highest-value first wedge, it scales to host and connect canon domains across product, HR, legal, security, sales enablement, and support.

---

## Why MsgStack?

When teams adopt AI for content generation and automation, a critical problem emerges: **AI agents don't know what is actually approved and true for your organization.**

- An SDR asks Claude to write a cold email. Claude doesn't know your positioning or legal constraints, so it freelances.
- A product engineer uses Copilot to draft release notes. It hallucinated integration details.
- A regional team uses ChatGPT to localize a datasheet. The output contradicts the latest security or compliance facts.

MsgStack fixes this by defining **the canon** — the authoritative, structured truth for each domain. Rather than letting AI tools guess or copy-paste from outdated, scattered PDFs, department SMEs (canon owners) curate their own domain content in MsgStack. MsgStack makes this canon **machine-readable and directly queryable** via the [Model Context Protocol](https://modelcontextprotocol.io/). Before any AI generates content, it queries the approved canon domain for headlines, policies, proof points, or personas, ensuring downstream outputs stay aligned.

---

## What it does

```
Source Document (PDF / DOCX / Drive)
         ↓  extract → LLM structure
Canon Domain / MessageHouse  (positioning · tagline · personas · key messages · pillars)
         ↓  embed → Turbovec  +  build → Knowledge Graph
    ┌─────────────────────────────────────────┐
    │  Semantic Search   │  Graph Traversal   │
    │  (vector approx.)  │  (verbatim exact)  │
    └────────────────────┴────────────────────┘
         ↓  skill template + grounding context + LLM
Derived Artifact  (one-pager · email · battlecard · LinkedIn · release notes · …)
```

**Two retrieval modes — neither approximates approved content:**
- **Vector (Turbovec):** local semantic similarity for exploratory queries — finds thematically relevant canon entries (in-process, <0.1ms database latency)
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

Connect any MCP-compatible AI and it gains access to the following tools. 

> [!NOTE]
> **Transitional Tool Names:** While the conceptual product layer uses **Canon Domains** and **Canon Entries**, the underlying code and tool names retain their transitional names (like `_house` and `_framework`) for backward compatibility with existing client configurations.

| Tool | What it does |
|------|-------------|
| `list_message_houses` | List all available Canon Domains — always call first to orient yourself |
| `search_messaging` | Semantic + keyword search across approved Canon Entries |
| `get_graph_connections` | Deterministic graph traversal — verbatim approved canon content |
| `set_active_house` | Pin a specific Canon Domain as active for the session |
| `get_message_house` | Retrieve a full Canon Domain for detailed research |
| `generate_artifact` | Generate a grounded artifact (datasheet, email, battlecard, post, …) from the active domain |
| `build_ui_artifact` | Get a visual HTML page URL for a generated artifact |
| `list_skills` | List available artifact types (skills) with required context parameters |
| `check_framework_completeness` | Score a Canon Domain against completeness specifications (0–100) |
| `compare_houses` | Side-by-side comparison of two or more Canon Domains |
| `get_grounding_context` | Current session state: active Canon Domain, used entries, confidence |
| `reset_conversation` | Clear current session state and start fresh |
| `get_framework_spec` | Full specification criteria for a complete Canon Domain |
| `list_channels` | All messaging and publishing channels including custom ones |

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
| **Dashboard** | Stats: Canon Domains, Canon Entries, personas; graph health widget |
| **Canon Domains** | Browse, create, edit, delete Canon Domains; tabbed detail (Overview / Entries / Personas) |
| **Artifacts** | Select Canon Domain + skill, generate, preview structured output, open visual page |
| **Upload** | Drop PDF / DOCX / TXT → auto-extract and structure into a Canon Domain via LLM; preview before saving |
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

## Data Model & Canon Schema

MsgStack's core architecture divides the conceptual layer from the implementation database models. The product layer exposes **Canon Domains** and **Canon Entries**, while the database layer leverages backward-compatible model names.

### Canon Domain (DB Table: `message_houses`)
The core concept is a **Canon Domain** — an authoritative domain of truth for a specific department or product. The database model implementing this is `MessageHouse`.

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Canon domain name |
| `document_type` | enum | Department schema category: `message_house` / `brand_guide` / `competitive_brief` / `corp_narrative` / `persona_library` |
| `positioning` | str | Foundational domain thesis or core positioning statement |
| `tagline` | str | Primary claim or punchy tagline (≤7 words) |
| `differentiation` | str | Core competitive claims or key differentiators |
| `audience` | str | Target persona wrapper description |
| `brand_personality` | str | Tone, voice, and style rules |
| `summary` | str | 2–3 sentence overview of the domain |
| `status` | enum | `active` / `archived` / `needs_review` |

### Canon Entry (DB Table: `key_messages`)
Individual approved units of canon truth, linked to a specific canon domain. The database model implementing this is `KeyMessage`.

| Field | Type | Description |
|-------|------|-------------|
| `section_type` | enum | Entry role: `headline` / `subhead` / `benefit` / `use_case` / `proof_point` / `objection` / `social_proof` / `positioning` |
| `priority` | int 1–5 | Importance ranking (1 = highest priority) |
| `content` | str | The approved canonical copy |
| `variants` | dict | Channel-specific rewrites: `{linkedin: "...", email: "..."}` |
| `personas` | list[str] | List of target personas this entry applies to |
| `channels` | list[enum] | `all` / `linkedin` / `email` / `landing` / `paid` / `twitter` / `blog` |

### Knowledge Graph Schema
The in-memory NetworkX DiGraph maps the organizational canon to resolve exact dependency relationships:
```
CanonDomain (MessageHouse)
  ├─[HAS_SECTION]──► Section ──[CONTAINS]──► CanonEntry (KeyMessage)
  │                                             ├─[ADDRESSES]──► Persona
  │                                             └─[APPLIES_TO]─► Channel
  ├─[HAS_PILLAR]───► MessagingPillar ──[GROUPS]──► CanonEntry
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
- `v0.9` — Governance & Alignment Engine (enforce approval workflows and score content against canon domains)
- `v1.0` — Competitive Intelligence & Cross-Department Canon (competitor ingestion, cross-department canon domains)

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
