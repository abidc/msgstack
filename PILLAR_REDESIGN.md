# Task: Messaging Pillar Entity Redesign

## Context

MsgStack MCP Server (`C:\Users\Abid\msgstack-mcp\`) is a FastMCP + FastAPI server that
structures marketing/messaging documents into a knowledge graph for LLM-grounded content
generation.

Current entity model:
- `MessageHouse` (the grounding source / messaging framework)
- `KeyMessage` (a chunk: headline, proof_point, use_case, benefit, stat, etc.)
- `Persona`
- `Channel`
- Graph: `MessageHouse -[CONTAINS]-> KeyMessage`

**The problem**: There is no `MessagingPillar` entity. Real message houses organise their
content into 3–5 named pillars (e.g. "Speed", "Security", "Scale"). Currently all chunks
are flat siblings with no pillar grouping, which loses structural meaning.

**Goal**: Add `MessagingPillar` as a first-class entity so the graph becomes:
```
MessageHouse -[CONTAINS]-> MessagingPillar -[CONTAINS]-> KeyMessage
```

---

## File Map

| Path | Purpose |
|------|---------|
| `src/store.py` | SQLAlchemy models + `Store` class (all DB ops) |
| `src/models.py` | Pydantic models for API responses |
| `src/grounding/structure.py` | LLM extraction: raw text → structured MessageHouse |
| `src/grounding/graph.py` | NetworkX DiGraph: `GraphEngine` |
| `src/web_app.py` | FastAPI app: all REST endpoints |
| `src/web/dashboard.html` | Single-page UI (Jinja2 rendered; all JS inline) |

---

## Step 1 — Database Schema

### 1a. New `pillars` table

Add this SQLAlchemy model to `src/store.py` alongside `MessageHouseModel` and
`KeyMessageModel`:

```python
class PillarModel(Base):
    __tablename__ = "pillars"
    id = Column(Integer, primary_key=True, autoincrement=True)
    house_id = Column(Integer, ForeignKey("message_houses.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)           # e.g. "Speed", "Security"
    description = Column(String, nullable=True)     # one-line summary of the pillar
    display_order = Column(Integer, default=0)      # for ordered rendering
```

### 1b. Add `pillar_id` FK to `key_messages`

Add a nullable FK column to `KeyMessageModel`:

```python
pillar_id = Column(Integer, ForeignKey("pillars.id", ondelete="SET NULL"), nullable=True)
```

### 1c. Migration in `Store.init()` / `_migrate()`

The store already has a `_migrate()` method that runs `ALTER TABLE` statements on startup.
Add two migration steps:

```python
# Create pillars table if not exists
conn.execute(text("""
    CREATE TABLE IF NOT EXISTS pillars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        house_id INTEGER NOT NULL REFERENCES message_houses(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        description TEXT,
        display_order INTEGER DEFAULT 0
    )
"""))

# Add pillar_id column to key_messages if missing
try:
    conn.execute(text("ALTER TABLE key_messages ADD COLUMN pillar_id INTEGER REFERENCES pillars(id) ON DELETE SET NULL"))
except Exception:
    pass  # column already exists
```

---

## Step 2 — Pydantic Models (`src/models.py`)

Add these to `src/models.py`:

```python
class Pillar(BaseModel):
    id: int
    house_id: int
    name: str
    description: str | None = None
    display_order: int = 0

class PillarCreate(BaseModel):
    name: str
    description: str | None = None
    display_order: int = 0

class PillarUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    display_order: int | None = None
```

---

## Step 3 — Store Methods (`src/store.py`)

Add these methods to the `Store` class:

```python
def create_pillar(self, house_id: int, name: str, description: str | None = None, display_order: int = 0) -> int:
    """Insert a new pillar, return its id."""

def list_pillars(self, house_id: int) -> list[PillarModel]:
    """Return all pillars for a house ordered by display_order."""

def update_pillar(self, pillar_id: int, **kwargs) -> bool:
    """Partial update. Returns True if row was found."""

def delete_pillar(self, pillar_id: int) -> bool:
    """Delete pillar; SET NULL cascades to key_messages. Returns True if found."""

def assign_chunk_to_pillar(self, chunk_id: int, pillar_id: int | None) -> bool:
    """Set key_messages.pillar_id. Pass None to unassign."""
```

---

## Step 4 — Graph Engine (`src/grounding/graph.py`)

In `GraphEngine.rebuild()`, after building chunk nodes, add pillar nodes and edges:

```python
pillars = store.list_pillars(house.id)
for pillar in pillars:
    pil_node = f"pillar:{pillar.id}"
    g.add_node(pil_node, type="MessagingPillar",
               id=str(pillar.id), name=pillar.name,
               description=pillar.description or "",
               house_id=str(house.id))
    g.add_edge(doc_node, pil_node, rel="CONTAINS")

# When adding chunk nodes, check if it belongs to a pillar
for msg in messages:
    chunk_node = f"chunk:{msg.id}"
    g.add_node(chunk_node, ...)
    if msg.pillar_id:
        pil_node = f"pillar:{msg.pillar_id}"
        if g.has_node(pil_node):
            g.add_edge(pil_node, chunk_node, rel="CONTAINS")
    else:
        g.add_edge(doc_node, chunk_node, rel="CONTAINS")  # ungrouped chunks still hang off house
```

Add to `NODE_COLORS` / `NODE_SIZES` in `graph.py` as needed. In `get_graph_data()` add
the `MessagingPillar` type serialization block:

```python
elif ntype == "MessagingPillar":
    entry.update({"name": attrs.get("name", ""),
                  "description": attrs.get("description", ""),
                  "house_id": attrs.get("house_id", "")})
```

---

## Step 5 — LLM Extraction (`src/grounding/structure.py`)

Find the function that calls the LLM to extract structured content from raw document text.

Update the system/user prompt to ask the model to identify pillar groupings. The LLM
response schema should include a `pillars` array. Each pillar has:
- `name` (string, 1–4 words, e.g. "Speed", "Enterprise Security")
- `description` (one sentence)
- `chunks` (list of chunk objects currently extracted — same format as before but nested
  under the pillar they belong to)

Example target JSON structure:
```json
{
  "house": { "name": "...", "tagline": "...", "summary": "...", "positioning": "..." },
  "pillars": [
    {
      "name": "Speed",
      "description": "We deliver faster outcomes than any alternative.",
      "chunks": [
        { "section_type": "headline", "content": "10× faster deployment", "priority": 1, "personas": [], "channels": [] },
        { "section_type": "proof_point", "content": "Customers report 3× faster time-to-value", "priority": 2, "personas": [], "channels": [] }
      ]
    }
  ],
  "ungrouped_chunks": []   // chunks the model couldn't assign to a pillar
}
```

In the extraction code, after receiving the LLM response:
1. For each pillar in `response["pillars"]`: call `store.create_pillar(house_id, pillar["name"], pillar["description"])`
2. For each chunk in `pillar["chunks"]`: create the `KeyMessage` row and call
   `store.assign_chunk_to_pillar(chunk_id, pillar_id)`
3. Ungrouped chunks go in with `pillar_id = None`

---

## Step 6 — REST API (`src/web_app.py`)

Add these endpoints:

```python
@app.get("/api/houses/{house_id}/pillars")
def list_pillars(house_id: int) -> list[Pillar]:
    ...

@app.post("/api/houses/{house_id}/pillars", status_code=201)
def create_pillar(house_id: int, body: PillarCreate) -> Pillar:
    ...

@app.patch("/api/houses/{house_id}/pillars/{pillar_id}")
def update_pillar(house_id: int, pillar_id: int, body: PillarUpdate) -> Pillar:
    ...

@app.delete("/api/houses/{house_id}/pillars/{pillar_id}", status_code=204)
def delete_pillar(house_id: int, pillar_id: int):
    ...

@app.patch("/api/chunks/{chunk_id}/pillar")
def assign_chunk_pillar(chunk_id: int, pillar_id: int | None = None):
    """Assign or unassign a chunk to a pillar. Pass pillar_id=null to unassign."""
    ...
```

---

## Step 7 — UI (`src/web/dashboard.html`)

### 7a. House detail — Messages tab

Currently the messages tab renders a flat list of all chunks. Change it to:

1. Fetch `GET /api/houses/{id}/pillars` alongside the existing chunks fetch
2. Group chunk rows under their pillar heading. Ungrouped chunks go under an "Ungrouped"
   section at the bottom
3. Each pillar heading should show the pillar name + description as a styled sub-header
   (use the existing `.card-title` + `.text-3` styles)
4. Add a drag-handle or simple "Move to pillar" dropdown per chunk row so users can
   reassign chunks interactively (calls `PATCH /api/chunks/{id}/pillar?pillar_id=X`)
5. Add a "+ Add Pillar" button that opens a minimal inline form (name + description)
   and calls `POST /api/houses/{id}/pillars`

### 7b. Graph Explorer

Add `MessagingPillar` to the Cytoscape node palette:

```javascript
const NODE_COLORS = {
    GroundingDocument: '#7c6af7',
    MessagingPillar:   '#f59e0b',   // amber — distinct from purple doc and teal chunk
    GroundingChunk:    '#34d399',
    Persona:           '#60a5fa',
    Channel:           '#f472b6',
};
const NODE_SIZES = {
    GroundingDocument: 42,
    MessagingPillar:   30,
    GroundingChunk:    18,
    Persona:           22,
    Channel:           22,
};
```

In `_showNodeDetail()`, add a case for `MessagingPillar` that renders name, description,
and house_id in the detail panel.

In the legend/filter section, add `MessagingPillar` as a filterable type.

---

## Acceptance Criteria

- [ ] Existing data (no pillars) still loads without error — `pillar_id` is nullable,
      ungrouped chunks still appear
- [ ] New documents extracted after this change have pillars auto-detected by the LLM
- [ ] Graph Explorer shows amber `MessagingPillar` nodes between doc and chunk nodes
- [ ] House detail messages tab groups chunks under pillar headings
- [ ] CRUD endpoints for pillars return correct HTTP status codes
- [ ] `store._migrate()` is idempotent — safe to restart the server multiple times

---

## Notes

- The project uses **SQLite** (not PostgreSQL) via SQLAlchemy — the `pillar_id` FK with
  `ON DELETE SET NULL` requires SQLite 3.26+ (available on all current Python installs)
- The `KeyMessageModel` already has `personas` and `channels` as JSON-serialised lists —
  follow the same pattern for any new list fields
- Do NOT add a migration dependency library — the existing bare `ALTER TABLE` try/except
  pattern in `_migrate()` is the project convention
- The LLM extraction prompt is in `src/grounding/structure.py` — read it carefully before
  modifying so you preserve all existing fields (personas, channels, priority, etc.)
- Rebuild Docker after changes: `docker compose build msgstack-mcp && docker compose up -d msgstack-mcp`
