# MsgStack ✦

<img width="1535" height="1024" alt="image" src="https://github.com/user-attachments/assets/2d3ffa32-9906-4efe-b0ad-ca621fc83fce" />


[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-3E4E80.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3E4E80.svg)](https://python.org)
[![FastMCP](https://img.shields.io/badge/MCP-FastMCP-3E4E80)](https://github.com/jlowin/fastmcp)
[![GitHub Stars](https://img.shields.io/github/stars/abidc/msgstack?style=social)](https://github.com/abidc/msgstack)

**The organizational canon layer for AI grounding.**

> Departments own their domains of truth. AI tools and content workflows ground on that canon. When canon changes, downstream outputs stay aligned.

MsgStack is an open source MCP server + admin UI that turns your organization's authoritative content (the **"canon"**) into a governed, machine-readable knowledge layer. Every AI tool on your team — Claude, Cursor, ChatGPT, or your own agents — queries it before generating content, so what comes out is anchored in approved truth: verbatim where it must be, flexible where it may be, and auditable either way. Product marketing message houses are the first wedge; the same model hosts canon domains for product, legal, HR, security, sales enablement, and support.

---

## Why MsgStack?

When teams adopt AI for content generation, a critical problem emerges: **AI agents don't know what is actually approved and true for your organization.**

- An SDR asks Claude to write a cold email. Claude doesn't know your positioning or legal constraints, so it freelances.
- A product engineer uses Copilot to draft release notes. It hallucinates integration details.
- A regional team uses ChatGPT to localize a datasheet. The output contradicts the latest security or compliance facts.

MsgStack fixes this by making the canon **structured, governed, and directly queryable** via the [Model Context Protocol](https://modelcontextprotocol.io/). Department SMEs curate their own domains; entries carry an approval lifecycle, a content tier that tells the LLM how much latitude it has, and a named owner (DRI). Before any AI generates content, it retrieves from the approved canon — and every query is logged.

---

## What it does

```
Source Document (PDF / DOCX / PPTX / XLSX / Drive)
         ↓  extract → LLM structure → conflict check against existing canon
   Canon Domain  (positioning · tagline · personas · canon entries · pillars)
         ↓  embed → Turbovec  +  build → Knowledge Graph
    ┌─────────────────────────────────────────┐
    │  Semantic Search   │  Graph Traversal   │
    │  (vector approx.)  │  (verbatim exact)  │
    └────────────────────┴────────────────────┘
         ↓  skill template + tier-annotated grounding context + LLM
Derived Artifact  (datasheet · email · battlecard · deck · post · …)
         ↓  alignment scoring · Tier 1 verbatim validation · query audit log
```

**Two retrieval modes — neither approximates approved content:**
- **Vector (Turbovec):** local in-process semantic similarity for exploratory queries — no external vector DB, <0.1ms query latency
- **Graph (NetworkX):** deterministic traversal for verbatim approved content — exact taglines, locked proof points, objection responses — never approximated

**Governance built in:**
- **Approval lifecycle** — `Draft → In Review → Approved / Locked / Outdated`; grounding and generation only see approved canon by default
- **Content tiers** — a per-entry generation contract: Tier 1 *Locked* (reproduce verbatim — enforced with post-generation validation), Tier 2 *Structured* (substance preserved), Tier 3 *Grounded* (full phrasing latitude)
- **Alignment scoring** — score any draft against the canon; hard vs. soft conflicts, with a paraphrased Tier 1 claim always a hard conflict
- **DRI ownership** — a named accountable person per entry/domain, with transfer trail and an unowned-items accountability view
- **Query audit log** — every grounding query recorded: caller, query, entries returned, confidence, latency
- **Sub-canons** — nested domains with four inheritance policies (full, selective override, vocabulary-constrained, autonomous)

---

## Quick Start

### Option A — Docker (recommended)

```bash
git clone https://github.com/abidc/msgstack.git
cd msgstack
cp .env.example .env
# Add OPENAI_API_KEY to .env (required)

docker compose up -d
```

→ Admin UI: `http://localhost:8001/`
→ MCP endpoint: `http://localhost:8001/mcp`

### Option B — Python

```bash
git clone https://github.com/abidc/msgstack.git
cd msgstack
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

Once connected, your AI assistant discovers all tools automatically via the `system_instructions` and `quick_start` prompts — including the content tier contract, so clients know Tier 1 entries must be reproduced verbatim.

---

## MCP Tools

| Tool | What it does |
|------|-------------|
| `list_canon_domains` | List all Canon Domains — call first to orient yourself |
| `search_canon` | Semantic + keyword search across approved Canon Entries (drafts hidden by default) |
| `get_graph_connections` | Deterministic graph traversal — verbatim approved Canon Entries |
| `set_active_domain` | Pin a Canon Domain as active for the session |
| `get_canon_domain` | Retrieve a full Canon Domain (entries carry status, tier, and DRI) |
| `compare_canon_domains` | Side-by-side comparison of Canon Domains |
| `generate_artifact` | Generate a derived output grounded in the active canon, with tier enforcement |
| `build_ui_artifact` | Get a visual HTML page URL for a generated artifact |
| `list_skills` | List available artifact types with required context parameters |
| `score_content_alignment` / `score_canon_alignment` | Score a draft against the approved canon — hard/soft conflict report |
| `check_canon_completeness` | Score a Canon Domain against the completeness spec (0–100) |
| `get_entry_history` | Full audit trail for a Canon Entry (status, tier, and DRI changes) |
| `get_query_audit_log` | Review grounding query activity — caller, entries returned, confidence |
| `get_grounding_context` | Current session state: active domain, used entries, confidence |
| `list_channels` / `list_departments` | Publication channels and department grounding types |
| `export_to_penpot` / `set_penpot_project` | Export a visual artifact to Penpot for design handoff |
| `get_framework_spec` / `list_mcp_tools` / `reset_conversation` | Spec, tool discovery, session reset |

*Legacy aliases (`list_message_houses`, `search_messaging`, `set_active_house`, `get_message_house`, `compare_houses`, `get_message_history`, `check_framework_completeness`) are preserved as deprecated delegates.*

### Artifact types (`skill_id`)

| Skill | Required context |
|-------|----------------|
| `one_pager` | — |
| `email_template` | `stage`: awareness \| consideration \| decision |
| `linkedin_post` | — |
| `battlecard` | `competitor`: competitor name |
| `press_release` | `announcement`: announcement summary |
| `blog_post` | `topic`: blog topic |
| `talk_track` | — |
| `objection_handler` | — |
| `executive_summary` | — |
| `partner_brief` | — |
| `event_brief` | `event_name`: event name |
| `faq_document` | — |
| `sales_deck` / `event_presentation` / `executive_readout` | — (rendered as reveal.js presentations) |

---

## Admin UI

Navigate to `http://localhost:8001/` for the web interface (styled with the [ATLAS design system](docs/BRAND_GUIDELINES.md) — ink on paper, night chapter dark mode):

| Section | What you can do |
|---------|----------------|
| **Dashboard** | Canon health gauge, stats, graph widget, Canon Navigator chat agent |
| **Canon Domains** | Browse by department, tabbed detail (Overview / Entries / Personas), status + tier + DRI controls |
| **Upload** | Drop PDF / DOCX / PPTX / XLSX → extract, structure, conflict-check, preview before saving |
| **Artifacts** | Pick domain + skill, tonal sliders, generate, preview, visual pages |
| **Alignment Scoring** | Paste a draft → per-section alignment report with hard/soft conflicts |
| **Governance** | DRI accountability view (unowned first) + filterable query audit log with CSV export |
| **Skills / Channels** | Manage artifact templates and publication channels |
| **Connections** | Google Drive folder sync — auto-ingest changed source documents |
| **Graph Explorer** | Interactive Cytoscape.js canon graph, drawn on night like a star chart |
| **Settings / API Keys** | Workspace brand tokens (colors, fonts, logo), scoped API keys, theme |

---

## Architecture

```
run_server.py            # PathRouter: /mcp → FastMCP, /* → FastAPI
├── src/server.py        # FastMCP — MCP tools + system_instructions/quick_start prompts
├── src/web_app.py       # FastAPI admin REST API
├── src/web/             # Jinja2 admin SPA (base.html tokens + dashboard.html)
│
├── src/models.py        # Pydantic models — CanonDomain, CanonEntry (status/tier/DRI), QueryAuditLog
├── src/store.py         # SQLAlchemy ORM → SQLite (default) / PostgreSQL, additive migrations
│
├── src/pipeline/
│   ├── extract.py       # PDF / DOCX / PPTX / XLSX / TXT → structured text
│   ├── structure.py     # Text → structured Canon Domain via LLM
│   ├── conflict.py      # Ingestion conflict detection vs existing canon
│   ├── generator.py     # Tier-annotated grounding → artifact + Tier 1 verbatim validation
│   ├── alignment.py     # Alignment scoring engine (hard/soft conflicts)
│   ├── vocabulary.py    # Controlled-vocabulary sweep on generated output
│   ├── agents.py        # Governance / Voice / Structure agents + Canon Navigator
│   └── skills.py        # JSON skill template manager
│
├── src/grounding/
│   ├── search.py        # Turbovec local vector search + keyword fallback
│   ├── graph.py         # NetworkX DiGraph — deterministic retrieval
│   ├── session.py       # In-memory grounding session
│   └── tools.py         # Grounding tool implementations + query audit hook
│
├── src/design/          # Design spec schema, template registry, Penpot sync
├── src/rendering/       # HTML / Fabric.js / reveal.js / Penpot renderers
├── src/sources/         # Source connectors (Google Drive sync)
└── seed_data/seed.py    # Sample canon domains for development
```

**Single server, two interfaces:**
- `POST /mcp` → FastMCP SSE transport (Claude, Cursor, any MCP client)
- `GET/POST /api/*` → FastAPI admin REST endpoints
- `GET /` → Admin single-page UI

---

## Data Model

### Canon Domain (`canon_domains`)

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Canon domain name |
| `grounding_type` | enum | `message_house` / `brand_guide` / `competitive_brief` / `corp_narrative` / `persona_library` |
| `positioning` / `tagline` / `differentiation` / `audience` / `brand_personality` | str | Brand foundation fields |
| `department` | str | Owning department (drives Browse UX and API-key scoping) |
| `parent_domain_id` + `inheritance_policy` | — | Sub-canons: `full` / `selective_override` / `vocab_constrained` / `autonomous` |
| `dri` | str | Directly Responsible Individual for the domain |
| `status` | enum | `active` / `archived` / `needs_review` |

### Canon Entry (`canon_entries`)

| Field | Type | Description |
|-------|------|-------------|
| `section_type` | enum | `headline` / `benefit` / `proof_point` / `objection` / `brand_voice` / `word_list` / … |
| `content` | str | The approved canonical copy |
| `status` | enum | `draft` / `in_review` / `approved` / `outdated` / `locked` — grounding sees approved+locked only |
| `content_tier` | enum | `tier_1_locked` (verbatim) / `tier_2_structured` / `tier_3_grounded` — required before approval |
| `dri` | str | Entry-level owner (falls back to the domain DRI) |
| `priority` | int 1–5 | Importance ranking |
| `variants` / `personas` / `channels` | — | Channel rewrites and targeting |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | **Yes** | — | LLM structuring, generation, embeddings |
| `DATABASE_URL` | No | `sqlite:///msgstack.db` | SQLAlchemy URL |
| `TURBOVEC_INDEX_PATH` | No | `data/msgstack_vectors.tvim` | Local vector index path |
| `MSGSTACK_BASE_URL` | No | `http://localhost:8001` | Base URL for artifact links |
| `MSGSTACK_AUTH_ENABLED` | No | `false` | API-key auth on admin endpoints |
| `QUERY_LOG_RETENTION_DAYS` | No | `90` | Query audit log retention (pruned on startup) |
| `LOG_FORMAT` | No | `text` | `text` or `json` |

---

## Development

```bash
pip install -r requirements.txt
python -c "from seed_data.seed import seed; seed()"   # sample data
python run_server.py                                  # combined server
pytest tests/                                         # test suite
ruff check src/                                       # lint
```

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full versioned roadmap.

**Current version: v0.9 (in progress)**

**Recently shipped:**
- `v0.8` — Visual Artifact Engine: Fabric.js canvas, reveal.js presentations, Penpot export, workspace brand tokens; Turbovec local vector search; Markdown translation layer for full-content RAG
- `v0.9 (wave 1)` — Alignment scoring engine, ingestion conflict detection, controlled vocabulary, sub-canons with inheritance, artifact-entry bindings with drift flagging, multi-agent layer + Canon Navigator
- `v0.9 (wave 2)` — Content tiering with verbatim enforcement, DRI ownership with transfer trail, query audit log, ATLAS design system across the app

**Coming next:**
- `v0.9` — Content SLA & freshness triggers, dual-output citation-marked review copy, tier-aware graph-only retrieval routing
- `v1.0` — Content CI/CD promotion pipeline, golden query dataset & retrieval benchmarking, identity-scoped retrieval (SSO/OIDC), cross-department grounding types (`engineering_spec`, `policy_shield`)

---

## License

[Apache 2.0](LICENSE) — free to use, self-host, modify, and distribute.

---

## Links

- 🌐 Website: [msgstack.ai](https://www.msgstack.ai)
- 📖 Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 🎨 Design system: [docs/BRAND_GUIDELINES.md](docs/BRAND_GUIDELINES.md)
- 🗺️ Roadmap: [ROADMAP.md](ROADMAP.md)
- 💬 Discussions: [GitHub Discussions](https://github.com/abidc/msgstack/discussions)
