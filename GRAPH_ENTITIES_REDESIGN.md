# Task: Promote PainPoint, BuyingTrigger, Objection to First-Class Graph Entities

## Context

MsgStack MCP Server (`C:\Users\Abid\msgstack-mcp\src\`).

The knowledge graph currently has these node types:
`GroundingDocument → MessagingPillar → GroundingChunk`, `Persona`, `Channel`

Three critical entities are **invisible to graph traversal** — they exist as JSON string
arrays on `PersonaModel` but are never turned into nodes:

```python
# src/store.py PersonaModel (~line 188)
pain_points: Mapped[list] = mapped_column(JSON, default=list)     # list of strings
buying_triggers: Mapped[list] = mapped_column(JSON, default=list) # list of strings
objections: Mapped[list] = mapped_column(JSON, default=list)      # list of strings
```

The goal: make these traversable nodes so the graph can answer
"which messages address the CISO's specific objection?" by traversing
`Persona → HAS_OBJECTION → Objection ← RESOLVES ← ProofPoint`.

This is a **two-phase** task. Implement Phase 1 fully. Implement Phase 2 fully.

---

## File Map

| Path | Purpose |
|------|---------|
| `src/store.py` | SQLAlchemy models + `Store` class. `PersonaModel` ~line 179. `_migrate()` handles schema evolution. |
| `src/models.py` | Pydantic API response models |
| `src/grounding/graph.py` | `GraphEngine.rebuild()` builds the NetworkX DiGraph from DB state |
| `src/pipeline/structure.py` | LLM extraction — `_STRUCTURE_PROMPT` and `_commit_structured_house()` in `web_app.py` |
| `src/web_app.py` | FastAPI app + `_commit_structured_house()` function |
| `src/web/dashboard.html` | Single-page UI. `NODE_COLORS`, `NODE_SIZES`, `_showNodeDetail()`, `_renderGraphExplorer()` |

---

## Phase 1 — Graph nodes from existing JSON data (no schema changes)

This phase requires **only changes to `graph.py` and `dashboard.html`**. No DB schema
changes. All existing data immediately gets the new nodes by reading the JSON arrays
already stored on PersonaModel.

### 1a. Restructure `GraphEngine.rebuild()` in `src/grounding/graph.py`

**Current order**: doc node → pillars → chunks (with lazy persona node creation) → personas

**New order**: doc node → pillars → personas (with full sub-nodes) → chunks

This is required because chunk→pain_point and chunk→objection edges (Phase 2) need the
sub-nodes to already exist when chunks are processed.

Replace the entire `rebuild()` method body with this logic:

```python
def rebuild(self) -> None:
    if not _NX_AVAILABLE:
        return
    from src.store import get_store
    store = get_store()

    g = nx.DiGraph()
    houses = store.list_houses()

    for house in houses:
        doc_node = f"doc:{house.id}"
        g.add_node(doc_node, type="GroundingDocument",
                   id=str(house.id), name=house.name,
                   document_type=str(house.document_type),
                   summary=house.summary)

        # ── Pillars ──────────────────────────────────────────────────────────
        pillars = store.list_pillars(house.id)
        pillar_map = {}
        for pillar in pillars:
            pil_node = f"pillar:{pillar.id}"
            g.add_node(pil_node, type="MessagingPillar",
                       id=str(pillar.id), name=pillar.name,
                       description=pillar.description or "",
                       house_id=str(house.id))
            g.add_edge(doc_node, pil_node, rel="CONTAINS")
            pillar_map[pillar.id] = pil_node

        # ── Personas + sub-nodes (BEFORE chunks so edges can reference them) ─
        personas = store.get_personas(house.id)
        for persona in personas:
            pnode = f"persona:{house.id}:{persona.name}"
            g.add_node(pnode, type="Persona", name=persona.name,
                       house_id=str(house.id),
                       description=getattr(persona, 'description', ''))
            g.add_edge(doc_node, pnode, rel="TARGETS")

            for i, pp_text in enumerate(persona.pain_points or []):
                pp_node = f"pain_point:{house.id}:{persona.name}:{i}"
                g.add_node(pp_node, type="PainPoint",
                           id=pp_node, content=str(pp_text),
                           persona_name=persona.name,
                           house_id=str(house.id))
                g.add_edge(pnode, pp_node, rel="HAS_PAIN_POINT")

            for i, tr_text in enumerate(persona.buying_triggers or []):
                tr_node = f"trigger:{house.id}:{persona.name}:{i}"
                g.add_node(tr_node, type="BuyingTrigger",
                           id=tr_node, content=str(tr_text),
                           persona_name=persona.name,
                           house_id=str(house.id))
                g.add_edge(pnode, tr_node, rel="HAS_TRIGGER")

            for i, ob in enumerate(persona.objections or []):
                ob_node = f"objection:{house.id}:{persona.name}:{i}"
                # objections may be strings (legacy) or dicts {statement, response}
                if isinstance(ob, dict):
                    statement = ob.get("statement", "")
                    response = ob.get("response", "")
                else:
                    statement = str(ob)
                    response = ""
                g.add_node(ob_node, type="Objection",
                           id=ob_node, statement=statement,
                           response=response,
                           persona_name=persona.name,
                           house_id=str(house.id))
                g.add_edge(pnode, ob_node, rel="HAS_OBJECTION")

        # ── Chunks ───────────────────────────────────────────────────────────
        messages = store.get_key_messages(house.id)
        for msg in messages:
            chunk_node = f"chunk:{msg.id}"
            g.add_node(chunk_node, type="GroundingChunk",
                       id=str(msg.id), content=msg.content,
                       section_type=str(msg.section_type),
                       priority=msg.priority)

            if msg.pillar_id and msg.pillar_id in pillar_map:
                g.add_edge(pillar_map[msg.pillar_id], chunk_node, rel="CONTAINS")
            else:
                g.add_edge(doc_node, chunk_node, rel="CONTAINS")

            for persona_name in (msg.personas or []):
                pnode = f"persona:{house.id}:{persona_name}"
                if not g.has_node(pnode):
                    g.add_node(pnode, type="Persona", name=persona_name,
                               house_id=str(house.id))
                    g.add_edge(doc_node, pnode, rel="TARGETS")
                g.add_edge(chunk_node, pnode, rel="ADDRESSES")

            for channel in (msg.channels or []):
                ch_str = str(channel)
                cnode = f"channel:{ch_str}"
                if not g.has_node(cnode):
                    g.add_node(cnode, type="Channel", name=ch_str)
                g.add_edge(chunk_node, cnode, rel="APPLIES_TO")

    self._graph = g
    self._built = True
    log.debug("Graph rebuilt: %d nodes, %d edges", g.number_of_nodes(), g.number_of_edges())
```

### 1b. Update `get_graph_data()` in `src/grounding/graph.py`

In the `ntype` dispatch block (the if/elif chain inside the nodes loop), add three new
cases after the `elif ntype == "Persona":` block:

```python
elif ntype == "PainPoint":
    entry.update({"content": (attrs.get("content") or "")[:150],
                  "persona_name": attrs.get("persona_name", ""),
                  "house_id": attrs.get("house_id", "")})
elif ntype == "BuyingTrigger":
    entry.update({"content": (attrs.get("content") or "")[:150],
                  "persona_name": attrs.get("persona_name", ""),
                  "house_id": attrs.get("house_id", "")})
elif ntype == "Objection":
    entry.update({"statement": (attrs.get("statement") or "")[:150],
                  "response": (attrs.get("response") or "")[:150],
                  "persona_name": attrs.get("persona_name", ""),
                  "house_id": attrs.get("house_id", "")})
```

Also update the label logic at the top of the nodes loop. Currently:
```python
label = attrs.get("name") or (content[:35] + "…" if len(content) > 35 else content) or nid
```
Change to:
```python
if ntype == "Objection":
    raw = attrs.get("statement", "") or ""
    label = (raw[:32] + "…") if len(raw) > 32 else raw or nid
elif ntype in ("PainPoint", "BuyingTrigger"):
    raw = attrs.get("content", "") or ""
    label = (raw[:32] + "…") if len(raw) > 32 else raw or nid
else:
    label = attrs.get("name") or (content[:35] + "…" if len(content) > 35 else content) or nid
```

### 1c. Update `src/web/dashboard.html` — graph explorer palette

Find `NODE_COLORS` and `NODE_SIZES` constants and add the three new types:

```javascript
const NODE_COLORS = {
    GroundingDocument: '#7c6af7',
    MessagingPillar:   '#f97316',
    GroundingChunk:    '#34d399',
    Persona:           '#60a5fa',
    Channel:           '#f472b6',
    PainPoint:         '#ef4444',   // red — a problem/pain
    BuyingTrigger:     '#22c55e',   // green — a positive signal
    Objection:         '#fb923c',   // amber-orange — a concern
};
const NODE_SIZES = {
    GroundingDocument: 42,
    MessagingPillar:   30,
    GroundingChunk:    18,
    Persona:           24,
    Channel:           22,
    PainPoint:         14,
    BuyingTrigger:     14,
    Objection:         14,
};
```

### 1d. Update `_showNodeDetail()` in `src/web/dashboard.html`

Add cases for the three new node types in `_showNodeDetail()`. Follow the existing pattern
(the function reads `n._raw` and populates `#graph-node-detail`). Add:

```javascript
} else if (type === 'PainPoint') {
    rows = `
        <tr><td style="color:var(--text-3);padding:6px 0;width:110px">Type</td>
            <td><span style="color:#ef4444;font-weight:600">Pain Point</span></td></tr>
        <tr><td style="color:var(--text-3);padding:6px 0">Persona</td>
            <td>${n.persona_name || '—'}</td></tr>
        <tr><td style="color:var(--text-3);padding:6px 0;vertical-align:top">Content</td>
            <td style="color:var(--text)">${n.content || '—'}</td></tr>
    `;
} else if (type === 'BuyingTrigger') {
    rows = `
        <tr><td style="color:var(--text-3);padding:6px 0;width:110px">Type</td>
            <td><span style="color:#22c55e;font-weight:600">Buying Trigger</span></td></tr>
        <tr><td style="color:var(--text-3);padding:6px 0">Persona</td>
            <td>${n.persona_name || '—'}</td></tr>
        <tr><td style="color:var(--text-3);padding:6px 0;vertical-align:top">Trigger</td>
            <td style="color:var(--text)">${n.content || '—'}</td></tr>
    `;
} else if (type === 'Objection') {
    rows = `
        <tr><td style="color:var(--text-3);padding:6px 0;width:110px">Type</td>
            <td><span style="color:#fb923c;font-weight:600">Objection</span></td></tr>
        <tr><td style="color:var(--text-3);padding:6px 0">Persona</td>
            <td>${n.persona_name || '—'}</td></tr>
        <tr><td style="color:var(--text-3);padding:6px 0;vertical-align:top">Objection</td>
            <td style="color:var(--text)">${n.statement || '—'}</td></tr>
        <tr><td style="color:var(--text-3);padding:6px 0;vertical-align:top">Response</td>
            <td style="color:var(--text-2)">${n.response || '<em>No response captured</em>'}</td></tr>
    `;
}
```

---

## Phase 2 — Normalized tables + chunk-to-node edges

Phase 2 adds DB tables so chunk→PainPoint and chunk→Objection edges survive rebuilds,
and updates the LLM extraction prompt to capture structured `{statement, response}` pairs
and tag each chunk with the pain points / objections it addresses.

### 2a. New SQLAlchemy models in `src/store.py`

Add after `PillarModel`:

```python
class PainPointModel(Base):
    __tablename__ = "pain_points"
    id = Column(Integer, primary_key=True, autoincrement=True)
    persona_id = Column(String(36), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)

class BuyingTriggerModel(Base):
    __tablename__ = "buying_triggers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    persona_id = Column(String(36), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)

class ObjectionModel(Base):
    __tablename__ = "objections"
    id = Column(Integer, primary_key=True, autoincrement=True)
    persona_id = Column(String(36), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    statement = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
```

Add two new JSON columns to `KeyMessageModel`:

```python
pain_point_ids: Mapped[list] = mapped_column(JSON, default=list)   # list of int pain_point IDs
objection_ids: Mapped[list] = mapped_column(JSON, default=list)    # list of int objection IDs
```

### 2b. Migration in `Store._migrate()`

Add these blocks in the `_migrate()` method (follow existing try/except pattern):

```python
# pain_points table
conn.execute(text("""
    CREATE TABLE IF NOT EXISTS pain_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        persona_id TEXT NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
        content TEXT NOT NULL
    )
"""))

# buying_triggers table
conn.execute(text("""
    CREATE TABLE IF NOT EXISTS buying_triggers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        persona_id TEXT NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
        content TEXT NOT NULL
    )
"""))

# objections table — note: statement + response (not just a string)
conn.execute(text("""
    CREATE TABLE IF NOT EXISTS objections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        persona_id TEXT NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
        statement TEXT NOT NULL,
        response TEXT
    )
"""))

# New columns on key_messages
for col in ("pain_point_ids", "objection_ids"):
    try:
        conn.execute(text(f"ALTER TABLE key_messages ADD COLUMN {col} JSON DEFAULT '[]'"))
    except Exception:
        pass
```

### 2c. Store methods in `src/store.py`

Add these methods to the `Store` class:

```python
def bulk_create_pain_points(self, persona_id: str, items: list[str]) -> list[int]:
    """Insert pain points for a persona, return list of new IDs."""

def bulk_create_buying_triggers(self, persona_id: str, items: list[str]) -> list[int]:
    """Insert buying triggers for a persona, return list of new IDs."""

def bulk_create_objections(self, persona_id: str,
                            items: list[dict]) -> list[int]:
    """Items are {statement: str, response: str|None}. Return list of new IDs."""

def delete_persona_sub_attrs(self, persona_id: str) -> None:
    """Delete all pain_points, buying_triggers, objections for a persona.
    Used before re-extracting to avoid duplicates."""

def update_chunk_links(self, chunk_id: str,
                       pain_point_ids: list[int],
                       objection_ids: list[int]) -> None:
    """Overwrite pain_point_ids and objection_ids on a key_message row."""

def list_pain_points(self, persona_id: str) -> list:
    """Return all PainPointModel rows for a persona."""

def list_objections(self, persona_id: str) -> list:
    """Return all ObjectionModel rows for a persona."""
```

### 2d. Pydantic models in `src/models.py`

```python
class PainPoint(BaseModel):
    id: int
    persona_id: str
    content: str

class BuyingTrigger(BaseModel):
    id: int
    persona_id: str
    content: str

class Objection(BaseModel):
    id: int
    persona_id: str
    statement: str
    response: str | None = None
```

### 2e. LLM extraction prompt — `src/pipeline/structure.py`

Update `_STRUCTURE_PROMPT` (the `message_house` prompt). Change the personas block from:

```json
"personas": [
  {
    "name": "Persona name",
    "pain_points": ["string"],
    "buying_triggers": ["string"],
    "objections": ["string"]
  }
]
```

To:

```json
"personas": [
  {
    "name": "Persona name",
    "description": "Role description",
    "pain_points": [
      "They struggle with X",
      "Manual Y process wastes 3 days per week"
    ],
    "buying_triggers": [
      "Upcoming compliance audit",
      "Board mandate to reduce operational costs"
    ],
    "objections": [
      {
        "statement": "This is too expensive for our budget",
        "response": "Customers typically recover the cost in 6 months through a 40% reduction in operational overhead"
      },
      {
        "statement": "We already have a solution for this",
        "response": "Our customers find we complement existing tools by handling the workflow automation layer they lack"
      }
    ]
  }
]
```

Also add these two fields to **every chunk** in both `pillars[].chunks[]` and
`ungrouped_chunks[]`:

```json
{
  "section_type": "...",
  "content": "...",
  "priority": 1,
  "personas": ["Persona Name"],
  "channels": ["all"],
  "addresses_pain_points": ["exact text of the pain point this message addresses, if any"],
  "resolves_objections": ["exact statement text of the objection this message resolves, if any"]
}
```

Add instructions to the prompt rules section:
```
- For each chunk, populate addresses_pain_points with the verbatim text of any pain
  point (from the personas list) that this message directly speaks to.
- Populate resolves_objections with the verbatim statement text of any objection this
  message helps overcome.
- Leave both arrays empty [] if the chunk is general and not specific to a pain/objection.
```

### 2f. Update `_commit_structured_house()` in `src/web_app.py`

This function is called after LLM extraction to persist the structured house to the DB.
Find it and make these changes:

**When creating each persona** (after `store.upsert_persona()`):

```python
# Clear old sub-attrs then re-insert (idempotent on re-extraction)
store.delete_persona_sub_attrs(str(persona_obj.id))

pp_ids = store.bulk_create_pain_points(
    str(persona_obj.id),
    [p if isinstance(p, str) else p.get("content", str(p))
     for p in persona_data.get("pain_points", [])]
)
store.bulk_create_buying_triggers(
    str(persona_obj.id),
    [t if isinstance(t, str) else t.get("content", str(t))
     for t in persona_data.get("buying_triggers", [])]
)
ob_items = []
for ob in persona_data.get("objections", []):
    if isinstance(ob, dict):
        ob_items.append({"statement": ob.get("statement", ""), "response": ob.get("response")})
    else:
        ob_items.append({"statement": str(ob), "response": None})
store.bulk_create_objections(str(persona_obj.id), ob_items)
```

**Build lookup tables** (before processing chunks) to resolve content strings → IDs:

```python
# Build content→id maps for fast lookup during chunk linking
pain_point_map: dict[str, int] = {}    # content.lower() → id
objection_map: dict[str, int] = {}     # statement.lower() → id

for persona_data in structured.personas:
    p_name = persona_data.get("name", "")
    persona_obj = ... # already resolved above
    for pp in store.list_pain_points(str(persona_obj.id)):
        pain_point_map[pp.content.strip().lower()] = pp.id
    for ob in store.list_objections(str(persona_obj.id)):
        objection_map[ob.statement.strip().lower()] = ob.id
```

**When creating each chunk**, resolve the references:

```python
pp_ids = [
    pain_point_map[txt.strip().lower()]
    for txt in chunk_data.get("addresses_pain_points", [])
    if txt.strip().lower() in pain_point_map
]
ob_ids = [
    objection_map[txt.strip().lower()]
    for txt in chunk_data.get("resolves_objections", [])
    if txt.strip().lower() in objection_map
]
store.update_chunk_links(str(chunk_id), pp_ids, ob_ids)
```

### 2g. Update `GraphEngine.rebuild()` for Phase 2 — chunk→node edges

In the chunks loop (after adding chunk→persona and chunk→channel edges), add:

```python
# Phase 2: edges to pain points and objections
for pp_id in (getattr(msg, 'pain_point_ids', None) or []):
    pp_node = f"pain_point_db:{pp_id}"
    if g.has_node(pp_node):
        g.add_edge(chunk_node, pp_node, rel="ADDRESSES")

for ob_id in (getattr(msg, 'objection_ids', None) or []):
    ob_node = f"objection_db:{ob_id}"
    if g.has_node(ob_node):
        g.add_edge(chunk_node, ob_node, rel="RESOLVES")
```

Update the persona sub-node creation loop to use DB IDs when available. When
`store.list_pain_points()` returns rows, use `f"pain_point_db:{pp.id}"` as the node ID
instead of the synthetic index-based ID. This makes the Phase 1 and Phase 2 node IDs
consistent:

```python
db_pain_points = store.list_pain_points(str(persona.id))
if db_pain_points:
    for pp in db_pain_points:
        pp_node = f"pain_point_db:{pp.id}"
        g.add_node(pp_node, type="PainPoint",
                   id=str(pp.id), content=pp.content,
                   persona_name=persona.name, house_id=str(house.id))
        g.add_edge(pnode, pp_node, rel="HAS_PAIN_POINT")
else:
    # Phase 1 fallback: create from JSON array with synthetic IDs
    for i, pp_text in enumerate(persona.pain_points or []):
        pp_node = f"pain_point:{house.id}:{persona.name}:{i}"
        ...
```

Apply the same DB-first / JSON-fallback pattern for buying_triggers and objections.

### 2h. New REST API endpoints in `src/web_app.py`

```python
@app.get("/api/personas/{persona_id}/pain-points")
def list_persona_pain_points(persona_id: str) -> list[PainPoint]:
    ...

@app.get("/api/personas/{persona_id}/objections")
def list_persona_objections(persona_id: str) -> list[Objection]:
    ...

@app.post("/api/houses/{house_id}/reindex", status_code=202)
def reindex_house(house_id: str):
    """Rebuild normalized pain_point/objection tables from existing JSON arrays.
    Use this to backfill Phase 2 data for documents extracted before this change."""
    ...
```

The `reindex` endpoint logic:
1. Load all personas for the house
2. For each persona: call `store.delete_persona_sub_attrs()`, then `bulk_create_pain_points()`,
   `bulk_create_buying_triggers()`, `bulk_create_objections()` from the JSON arrays
3. Trigger a graph rebuild: `get_graph_engine().rebuild()`
4. Return `{"status": "ok", "personas_reindexed": N}`

---

## Acceptance Criteria

### Phase 1
- [ ] Graph explorer shows `PainPoint` (red), `BuyingTrigger` (green), `Objection` (amber) nodes for all existing data — no re-extraction required
- [ ] Clicking a PainPoint node shows its content and which persona it belongs to
- [ ] Clicking an Objection node shows statement and response (response will be empty for existing data until Phase 2)
- [ ] `graph.py rebuild()` no longer creates persona nodes lazily mid-chunk-loop — all persona nodes are built in the dedicated personas pass

### Phase 2
- [ ] New documents extracted after this change have `{statement, response}` pairs in Objection nodes
- [ ] Chunks with `addresses_pain_points` populated get `ADDRESSES` edges to PainPoint nodes in the graph
- [ ] Chunks with `resolves_objections` populated get `RESOLVES` edges to Objection nodes
- [ ] `POST /api/houses/{id}/reindex` backfills normalized tables for existing data
- [ ] `_migrate()` is idempotent — safe to restart the server multiple times

---

## Notes

- **Do not remove** `pain_points`, `buying_triggers`, `objections` JSON columns from
  `PersonaModel` — they are used throughout the UI (persona detail view, snapshot diffs,
  the `get_house_context()` method). The normalized tables are additive, not replacements.
- The `objection` section_type in `key_messages` is **not deprecated** by this change.
  Objection *chunks* (content someone wrote describing an objection) are different from
  Objection *nodes* (structured {statement, response} pairs extracted from personas). Both
  can coexist. In a later pass, `objection` chunks could be linked to their corresponding
  Objection node, but that is out of scope here.
- The `store.list_pain_points()` etc. methods return ORM model instances. Access their
  fields as attributes (`.content`, `.statement`, `.id`) not dict keys.
- Rebuild Docker after all changes: `docker compose build msgstack-mcp && docker compose up -d msgstack-mcp`
