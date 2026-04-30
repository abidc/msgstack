# Task: v0.7 Backend Implementation — Claude Code

**Project:** MsgStack MCP Server  
**Location:** `C:\Users\Abid\msgstack-mcp\`  
**Goal:** Implement the v0.7 hybrid Knowledge Graph + Vector RAG backend, plus the Multi-Content-Type data model foundation.

---

## Context

MsgStack MCP is a FastMCP + FastAPI server that stores brand messaging frameworks ("Message Houses") in SQLite and exposes MCP tools for AI grounding and artifact generation. The v0.7 milestone adds:

1. A knowledge graph layer (`src/grounding/graph.py`) for deterministic retrieval of verbatim approved content
2. A `document_type` discriminator so the store can hold brand guides, competitive briefs, corp narratives, and persona libraries alongside message houses
3. A `ChannelModel` DB table replacing the code-only `Channel` enum

Before touching any file, read the relevant source:
- `src/models.py` — Pydantic models, SectionType enum, Channel enum
- `src/store.py` — SQLAlchemy ORM, Store class, `init_store()` / `get_store()`
- `src/grounding/search.py` — existing hybrid search
- `src/server.py` — MCP tools (FastMCP)
- `src/web_app.py` — REST API endpoints

---

## Work Stream 1: Data Model Migration

### 1a. Add `DocumentType` enum to `src/models.py`

Add after the `HouseStatus` enum (line ~33):

```python
class DocumentType(str, Enum):
    MESSAGE_HOUSE = "message_house"
    BRAND_GUIDE = "brand_guide"
    COMPETITIVE_BRIEF = "competitive_brief"
    CORP_NARRATIVE = "corp_narrative"
    PERSONA_LIBRARY = "persona_library"
```

Add `document_type` field to `MessageHouse` Pydantic model:

```python
document_type: DocumentType = DocumentType.MESSAGE_HOUSE
```

### 1b. Expand `SectionType` enum in `src/models.py`

Append to the existing `SectionType` enum:

```python
# brand guide
BRAND_VOICE = "brand_voice"
STYLE_RULE = "style_rule"
WORD_LIST = "word_list"
# corp narrative
NARRATIVE_PILLAR = "narrative_pillar"
COMPANY_VALUE = "company_value"
FOUNDING_STORY = "founding_story"
# competitive brief
COMPETITOR_STRENGTH = "competitor_strength"
COMPETITOR_WEAKNESS = "competitor_weakness"
COMPETITIVE_RESPONSE = "competitive_response"
# persona library
PERSONA_DETAIL = "persona_detail"
```

### 1c. Add `document_type` column to `MessageHouseModel` in `src/store.py`

Find the SQLAlchemy `MessageHouseModel` class. Add:

```python
document_type: Mapped[str] = mapped_column(String, default="message_house", nullable=False, server_default="message_house")
```

This is backward-compatible — existing rows get the default. No migration script needed for SQLite (ALTER TABLE ADD COLUMN with DEFAULT works).

### 1d. Create `ChannelModel` in `src/store.py`

Add a new SQLAlchemy model for channels before `MessageHouseModel`:

```python
class ChannelModel(Base):
    __tablename__ = "channels"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

In `Store._init_db()` (or `init_store()` startup), seed default channels if table is empty:

```python
DEFAULT_CHANNELS = ["all", "email", "linkedin", "twitter", "paid_ads", "landing_page", "sales_deck"]
```

Add Store methods:
- `get_channels() -> list[ChannelModel]`
- `upsert_channel(id, name, description) -> ChannelModel`
- `delete_channel(id) -> bool`

### 1e. Add CRUD endpoints for Channels in `src/web_app.py`

```
GET  /api/channels        → list all channels
POST /api/channels        → create channel {id, name, description}
PATCH /api/channels/{id}  → update channel
DELETE /api/channels/{id} → delete channel (reject if is_default=True)
```

---

## Work Stream 2: Knowledge Graph Engine

### 2a. Create `src/grounding/graph.py`

This file does not yet exist. Create it.

**Design:** NetworkX in-memory directed graph, rebuilt from SQLite on startup and after any mutation. No new database tables — derives graph state entirely from the existing `message_houses`, `key_messages`, `personas` tables (plus the new `channels` table). SQLite is the source of truth; the graph is a derived read layer.

```python
"""Knowledge graph engine for deterministic grounding retrieval."""

import networkx as nx
from typing import Any
from src.store import get_store
from src.models import DocumentType


class GraphEngine:
    def __init__(self):
        self._graph: nx.DiGraph = nx.DiGraph()
        self._built = False

    def rebuild(self) -> None:
        """Rebuild the in-memory graph from SQLite store."""
        store = get_store()
        g = nx.DiGraph()

        for house in store.list_houses():
            g.add_node(f"doc:{house.id}", type="GroundingDocument",
                       name=house.name, document_type=house.document_type,
                       summary=house.summary)

            for msg in store.get_messages(house.id):
                g.add_node(f"chunk:{msg.id}", type="GroundingChunk",
                           content=msg.content, section_type=msg.section_type,
                           priority=msg.priority)
                g.add_edge(f"doc:{house.id}", f"chunk:{msg.id}", rel="CONTAINS")

                for persona_name in (msg.personas or []):
                    pnode = f"persona:{house.id}:{persona_name}"
                    g.add_node(pnode, type="Persona", name=persona_name)
                    g.add_edge(f"chunk:{msg.id}", pnode, rel="ADDRESSES")

                for channel in (msg.channels or []):
                    cnode = f"channel:{channel}"
                    g.add_node(cnode, type="Channel", name=channel)
                    g.add_edge(f"chunk:{msg.id}", cnode, rel="APPLIES_TO")

            for persona in store.get_personas(house.id):
                pnode = f"persona:{house.id}:{persona.name}"
                if not g.has_node(pnode):
                    g.add_node(pnode, type="Persona", name=persona.name,
                               pain_points=persona.pain_points,
                               buying_triggers=persona.buying_triggers)
                g.add_edge(f"doc:{house.id}", pnode, rel="TARGETS")

        self._graph = g
        self._built = True

    def _ensure_built(self) -> None:
        if not self._built:
            self.rebuild()

    def get_chunks_for_house(self, house_id: str) -> list[dict]:
        """Deterministic: return all chunks for a house via graph traversal."""
        self._ensure_built()
        doc_node = f"doc:{house_id}"
        if doc_node not in self._graph:
            return []
        chunks = []
        for _, chunk_node, data in self._graph.out_edges(doc_node, data=True):
            if data.get("rel") == "CONTAINS":
                attrs = self._graph.nodes[chunk_node]
                chunks.append({"id": chunk_node.split(":", 1)[1], **attrs})
        return sorted(chunks, key=lambda c: c.get("priority", 3))

    def get_chunks_for_persona(self, house_id: str, persona_name: str) -> list[dict]:
        """Return chunks that ADDRESS a specific persona within a house."""
        self._ensure_built()
        persona_node = f"persona:{house_id}:{persona_name}"
        if persona_node not in self._graph:
            return []
        chunks = []
        for chunk_node, _, data in self._graph.in_edges(persona_node, data=True):
            if data.get("rel") == "ADDRESSES":
                attrs = self._graph.nodes[chunk_node]
                chunks.append({"id": chunk_node.split(":", 1)[1], **attrs})
        return chunks

    def get_chunks_for_channel(self, house_id: str, channel: str) -> list[dict]:
        """Return chunks that APPLY_TO a specific channel within a house."""
        self._ensure_built()
        channel_node = f"channel:{channel}"
        doc_node = f"doc:{house_id}"
        if channel_node not in self._graph:
            return []
        chunks = []
        doc_chunks = {n for _, n, d in self._graph.out_edges(doc_node, data=True)
                      if d.get("rel") == "CONTAINS"}
        for chunk_node, _, data in self._graph.in_edges(channel_node, data=True):
            if data.get("rel") == "APPLIES_TO" and chunk_node in doc_chunks:
                attrs = self._graph.nodes[chunk_node]
                chunks.append({"id": chunk_node.split(":", 1)[1], **attrs})
        return chunks

    def get_stats(self) -> dict:
        """Graph statistics for the dashboard widget."""
        self._ensure_built()
        g = self._graph
        by_type: dict[str, int] = {}
        for _, attrs in g.nodes(data=True):
            t = attrs.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "nodes": g.number_of_nodes(),
            "edges": g.number_of_edges(),
            "by_type": by_type,
        }


_graph_engine: GraphEngine | None = None


def get_graph_engine() -> GraphEngine:
    global _graph_engine
    if _graph_engine is None:
        _graph_engine = GraphEngine()
    return _graph_engine


def invalidate_graph() -> None:
    """Call after any mutation to message_houses / key_messages / personas."""
    engine = get_graph_engine()
    engine._built = False
```

### 2b. Wire `invalidate_graph()` into store mutations

In `src/store.py`, after any call to `upsert_house()`, `upsert_key_message()`, `upsert_persona()`, `delete_house()`, `delete_message()`, `delete_persona()`, call:

```python
from src.grounding.graph import invalidate_graph
invalidate_graph()
```

Import lazily inside the function body to avoid circular imports.

### 2c. Update `search_messaging` in `src/grounding/search.py`

Add a `retrieval_mode: str = "hybrid"` parameter (values: `"vector"`, `"graph"`, `"hybrid"`, `"keyword"`).

- `"graph"` mode: call `get_graph_engine().get_chunks_for_house(house_id)` and return results as `GroundingResult` objects (confidence=1.0, no approximation).
- `"hybrid"` mode (default): run vector search, then augment with graph results for any section_types with priority ≤ 2 that weren't returned by vector search.
- `"vector"` mode: existing behavior unchanged.
- `"keyword"` mode: existing SQLite keyword fallback.

---

## Work Stream 3: MCP Tools

### 3a. Add graph tools to `src/server.py`

Add two new MCP tools:

**`get_graph_connections`** — Deterministic graph lookup:
```
Parameters: house_id (str), persona (str | None), channel (str | None)
Returns: list of GroundingChunk content strings, retrieved via graph traversal (not vector search)
Use case: when an AI agent needs verbatim approved messaging for a specific persona/channel combo
```

**`list_channels`** — Return available channels:
```
Parameters: none
Returns: list of {id, name, description} from the channels DB table
```

Add `retrieval_mode` parameter to the existing `search_messaging` tool, defaulting to `"hybrid"`.

---

## Work Stream 4: Graph Stats API Endpoint

Add to `src/web_app.py`:

```
GET /api/graph/stats  → returns get_graph_engine().get_stats()
GET /api/graph/house/{house_id}  → returns get_graph_engine().get_chunks_for_house(house_id) (for UI visualization)
POST /api/graph/rebuild  → calls get_graph_engine().rebuild() explicitly (admin action)
```

---

## Dependencies

Add to `requirements.txt` or `pyproject.toml`:
```
networkx>=3.0
```

NetworkX is pure Python — no native binaries, safe to add without Docker build concerns.

---

## Testing

After implementing:
1. `docker compose build && docker compose up -d` to rebuild
2. `docker logs -f msgstack-mcp` — confirm no import errors
3. Hit `GET /api/graph/stats` — should return node/edge counts
4. Hit `GET /api/channels` — should return the 7 seeded defaults
5. Upload a DOCX — confirm `invalidate_graph()` is called and graph rebuilds

Do not break existing `/api/houses` or MCP tool behavior. All changes are additive.
