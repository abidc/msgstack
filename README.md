# MsgStack ✦

<img width="1535" height="1024" alt="image" src="https://github.com/user-attachments/assets/2d3ffa32-9906-4efe-b0ad-ca621fc83fce" />


[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-3E4E80.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3E4E80.svg)](https://python.org)
[![FastMCP](https://img.shields.io/badge/MCP-FastMCP-3E4E80)](https://github.com/jlowin/fastmcp)
[![GitHub Stars](https://img.shields.io/github/stars/abidc/msgstack?style=social)](https://github.com/abidc/msgstack)

**A self-hosted memory layer for your agents.**

> Facts about your services — API constraints, SLAs, deprecation timelines, config defaults — stored as typed nodes in a graph. Agents query it over MCP. When one fact changes, everything downstream that depends on it is invalidated automatically.

MsgStack is an open source MCP server + admin UI. It turns the things your team knows about its services into **assertions**: atomic, typed, versioned facts that live in **specs** and are connected by typed **edges**. Retrieval fuses vector search with graph traversal, so an agent asking about a rate limit also finds the gateway policy that constrains it — even when that lives in a different spec.

---

## Why MsgStack?

Teams ship faster than their documentation. The facts an agent needs are scattered across Confluence, Jira, Slack and stale READMEs, and RAG over that pile returns confident, unversioned, unattributable answers.

- A copilot drafts release notes and invents a rate limit that was lowered last sprint.
- A support agent quotes an SLA from a page nobody has reviewed in a year.
- An integration guide keeps promising a parameter that was deprecated two versions ago.

The common failure is not retrieval quality. It is that **a fact has dependencies and an embedding does not**. Vector search finds text resembling your question; it cannot tell you the number you just quoted is downstream of a policy that changed on Tuesday.

MsgStack stores facts as typed nodes with typed relationships — `DEPENDS_ON`, `SUPERSEDES`, `CONTRADICTS` — and walks them. Retrieval crosses spec boundaries. Edits cascade.

---

## What it does

```
Source Document (PDF / DOCX / MD / Drive)
         ↓  extract → LLM structure → conflict check against existing assertions
   Spec  (positioning · audiences · assertions · pillars)
         ↓  embed → Turbovec        build → Knowledge Graph (NetworkX)
    ┌──────────────────────┬──────────────────────────────────┐
    │   Vector recall      │  Graph traversal                 │
    │   (open questions)   │  (dependencies, cross-spec)      │
    └──────────┬───────────┴───────────────┬──────────────────┘
               └── reciprocal rank fusion ─┘
         ↓  skill template + tier-annotated grounding context + LLM
Derived Artifact  (release notes · ADR · runbook · changelog · …)
         ↓  alignment scoring · Tier 1 verbatim validation
```

**Retrieval is two routes, fused.** Vector recall answers open questions. Graph
traversal answers dependency questions — and crosses spec boundaries, so an
assertion in another spec that shares an entity or sits behind a `DEPENDS_ON`
edge can surface. Results found by both routes rank above results found by
either alone.

**Typed relationships.** `DEPENDS_ON`, `INFORMS`, `SUPERSEDES`, `CONTRADICTS`,
`OWNS`, `IMPLEMENTS`, `MENTIONS` — each with confidence and provenance.

**Change propagation.** `DEPENDS_ON` and `INFORMS` cascade staleness: edit an
assertion and everything downstream is marked outdated, transitively, across
specs, and drops out of grounding results. The other relationships are
navigational.

**Content tiers.** A per-assertion generation contract: Tier 1 *Locked*
(reproduced verbatim, validated after generation), Tier 2 *Structured*
(substance preserved), Tier 3 *Grounded* (full phrasing latitude).

**Assertion types.** `constraint`, `sla`, `deprecation`, `config_default`,
`dependency`, `capability`, `limitation`, `security_posture`,
`interface_contract`, `version_policy`, `runbook_step`, `decision`.

**Not included, deliberately.** No RBAC, no approval routing, no SLA breach
notifications, no compliance audit log. This is a developer tool, not a
governance platform — see `STRATEGY_V2.md`.

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
| `list_specs` | List all Specs — call first to orient yourself |
| `search_assertions` | Fused retrieval: vector recall + graph expansion across Specs |
| `traverse_graph` | Walk typed edges outward from one or more Assertions; returns the path to each result |
| `get_impact` | Blast radius before you edit — what goes stale if this changes |
| `link_assertions` | Create a typed edge (`DEPENDS_ON`, `SUPERSEDES`, `CONTRADICTS`, …) |
| `get_graph_connections` | Structural view of one Spec — sections, audiences, channels |
| `set_active_spec` | Pin a Spec as active for the session |
| `get_spec` | Retrieve a full Spec (assertions carry status, tier, owner) |
| `compare_specs` | Side-by-side comparison of Specs |
| `generate_artifact` | Generate a derived output grounded in the active Spec, with tier enforcement |
| `build_ui_artifact` | Get a visual HTML page URL for a generated artifact |
| `list_skills` | List available artifact types with required context parameters |
| `score_alignment` / `score_alignment_report` | Score a draft against approved Assertions — JSON or markdown |
| `check_spec_completeness` | Score a Spec against the schema (0–100) |
| `get_assertion_history` | Change trail for an Assertion (status and tier transitions) |
| `get_grounding_context` | Current session state: active Spec, used Assertions, confidence |
| `list_channels` / `list_departments` | Publication channels and department schemas |
| `export_to_penpot` / `set_penpot_project` | Export a visual artifact to Penpot for design handoff |
| `get_schema` / `list_mcp_tools` / `reset_conversation` | Schema, tool discovery, session reset |

*The `message_house` / `spec_id` aliases from the pre-v1 vocabulary have been
removed. `canon_*` field names are accepted for one more version.*

### Artifact types (`skill_id`)

| Skill | Required context |
|-------|----------------|
| `release_notes` | — |
| `api_changelog` | — |
| `deprecation_notice` | — |
| `adr` | — |
| `incident_comms` | — |
| `runbook` | — |
| `rfc_summary` | — |
| `onboarding_doc` | — |
| `integration_guide` | — |
| `faq_document` / `executive_summary` / `one_pager` / `blog_post` | — |

*The product-marketing templates (battlecard, sales_deck, press_release,
linkedin_post, …) were retired in v2 and archived under
`data/archive/skills-pmm/`.*

---

## Admin UI

Navigate to `http://localhost:8001/` for the web interface (styled with the [ATLAS design system](docs/BRAND_GUIDELINES.md) — ink on paper, night chapter dark mode):

| Section | What you can do |
|---------|----------------|
| **Dashboard** | Graph health gauge, stats, graph widget, Graph Navigator chat agent |
| **Specs** | Browse by department, tabbed detail (Overview / Assertions / Audiences), status + tier + owner controls |
| **Upload** | Drop PDF / DOCX / PPTX / XLSX → extract, structure, conflict-check, preview before saving |
| **Artifacts** | Pick domain + skill, tonal sliders, generate, preview, visual pages |
| **Alignment Scoring** | Paste a draft → per-section alignment report with hard/soft conflicts |
| **Skills / Channels** | Manage artifact templates and publication channels |
| **Connections** | Google Drive folder sync — auto-ingest changed source documents |
| **Graph Explorer** | Interactive Cytoscape.js graph graph, drawn on night like a star chart |
| **Settings / API Keys** | Workspace brand tokens (colors, fonts, logo), scoped API keys, theme |

---

## Architecture

```
run_server.py            # PathRouter: /mcp → FastMCP, /* → FastAPI
├── src/server.py        # FastMCP — MCP tools + system_instructions/quick_start prompts
├── src/web_app.py       # FastAPI admin REST API
├── src/web/             # Jinja2 admin SPA (base.html tokens + dashboard.html)
│
├── src/models.py        # Pydantic models — Spec, Assertion, Entity, Edge, RelType
├── src/store.py         # SQLAlchemy ORM → SQLite (default) / PostgreSQL, additive migrations
│
├── src/pipeline/
│   ├── extract.py       # PDF / DOCX / PPTX / XLSX / TXT → structured text
│   ├── structure.py     # Text → structured Spec via LLM
│   ├── conflict.py      # Ingestion conflict detection vs existing graph
│   ├── generator.py     # Tier-annotated grounding → artifact + Tier 1 verbatim validation
│   ├── alignment.py     # Alignment scoring engine (hard/soft conflicts)
│   ├── vocabulary.py    # Controlled-vocabulary sweep on generated output
│   ├── agents.py        # Voice / Structure agents + Graph Navigator
│   └── skills.py        # JSON skill template manager
│
├── src/grounding/
│   ├── search.py        # Turbovec local vector search + keyword fallback
│   ├── graph.py         # NetworkX DiGraph — deterministic retrieval
│   ├── session.py       # In-memory grounding session
│   └── tools.py         # Grounding tool implementations
│
├── src/design/          # Design spec schema, template registry, Penpot sync
├── src/rendering/       # HTML / Fabric.js / reveal.js / Penpot renderers
├── src/sources/         # Source connectors (Google Drive sync)
└── seed_data/seed.py    # Sample specs for development
```

**Single server, two interfaces:**
- `POST /mcp` → FastMCP SSE transport (Claude, Cursor, any MCP client)
- `GET/POST /api/*` → FastAPI admin REST endpoints
- `GET /` → Admin single-page UI

---

## Data Model

### Spec (`specs`)

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Spec name |
| `schema_type` | enum | `engineering_spec` / `brand_guide` / `competitive_brief` / `corp_narrative` / `persona_library` |
| `positioning` / `tagline` / `differentiation` / `audience` / `brand_personality` | str | Brand foundation fields |
| `department` | str | Owning department (drives Browse UX and API-key scoping) |
| `parent_domain_id` + `inheritance_policy` | — | Child specs: `full` / `selective_override` / `vocab_constrained` / `autonomous` |
| `dri` | str | Directly Responsible Individual for the domain |
| `status` | enum | `active` / `archived` / `needs_review` |

### Assertion (`assertions`)

| Field | Type | Description |
|-------|------|-------------|
| `assertion_type` | enum | `headline` / `benefit` / `proof_point` / `objection` / `brand_voice` / `word_list` / … |
| `content` | str | The approved canonical copy |
| `status` | enum | `draft` / `in_review` / `approved` / `outdated` / `locked` — grounding sees approved+locked only |
| `content_tier` | enum | `tier_1_locked` (verbatim) / `tier_2_structured` / `tier_3_grounded` — required before approval |
| `dri` | str | Assertion-level owner (falls back to the Spec owner) |
| `priority` | int 1–5 | Importance ranking |
| `variants` / `audiences` / `channels` | — | Channel rewrites and targeting |

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
- `v0.9 (wave 1)` — Alignment scoring engine, ingestion conflict detection, controlled vocabulary, child specs with inheritance, artifact-entry bindings with drift flagging, multi-agent layer + Graph Navigator
- `v0.9 (wave 2)` — Content tiering with verbatim enforcement, ATLAS design system across the app

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
