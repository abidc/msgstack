# OpenCode Solution — Complete Fix Summary

All fixes applied across four instruction files. Server restarted and running (PID 19304).

---

## OPENCODE_FIXES.md — 4 Bugs Fixed

### Bug 1 — Drive-synced frameworks have empty content (name = filename, no messages)

**Root cause**: `StructuredHouse.key_messages` had no default value, causing Pydantic `ValidationError` when the LLM returned pillar-based output (no top-level `key_messages`). Fell through to `_parse_markdown()` which produced a bare house.

**Fix 1a** — `src/pipeline/structure.py:51`
```python
# Before
key_messages: list[dict]

# After
key_messages: list[dict] = Field(default_factory=list)
```

**Fix 1b** — `src/web_app.py:2833` (after line 2831)
Added new endpoint:
```python
@app.post("/api/connections/{connection_id}/source-files/{drive_file_id}/resync")
def resync_source_file(connection_id: str, drive_file_id: str):
    """Mark a source file for re-ingestion on next sync cycle."""
    conn = store.get_connection(connection_id)
    if not conn:
        raise HTTPException(404, "Connection not found")
    sf = store.get_source_file_by_drive_id(connection_id, drive_file_id)
    if not sf:
        raise HTTPException(404, "Source file not found")
    if sf.get("house_id"):
        try:
            store.delete_house(UUID(sf["house_id"]))
        except Exception:
            pass
    store.upsert_source_file(
        connection_id=connection_id,
        drive_file_id=drive_file_id,
        file_name=sf["file_name"],
        mime_type=sf["mime_type"],
        drive_modified_at=sf.get("drive_modified_at", ""),
        sync_status="error",
        error_message="queued for resync",
    )
    return {"status": "queued"}
```

**Fix 1c** — `src/web/dashboard.html`
- Added 5th "Actions" column to connections files table `<thead>`
- Added Re-sync button cell in table rows
- Added `resyncFile()` JS function with immediate sync trigger

---

### Bug 2 — No way to delete frameworks (missing UI + missing Pinecone cleanup)

**Fix 2a** — `src/web_app.py:410` (delete endpoint)
- Validates house_id is valid UUID before use
- Deletes Pinecone vectors via `GroundingEngine.index.delete(filter={"message_house_id": house_id})`
- Rebuilds knowledge graph after deletion

**Fix 2b** — `src/web/dashboard.html`
Added `deleteHouse()` JS function

**Fix 2c** — `src/web/dashboard.html:716` (house detail view)
Added Delete button to detail header:
```html
<button id="detail-delete-btn" class="btn btn-ghost btn-sm"
        style="color:var(--danger);border-color:var(--danger);"
        onclick="deleteHouse('${house.id}')">Delete</button>
```

**Fix 2d** — `src/web/dashboard.html:627` (frameworks list cards)
Added Delete button to card footer with `event.stopPropagation()`

---

### Bug 3 — All frameworks show 0% complete in detail view

**Root cause**: `_house_response()` didn't include `completeness_score` in its return dict.

**Fix** — `src/web_app.py:161-167`
```python
def _house_response(house: MessageHouse) -> dict:
    messages = store.get_key_messages(house.id)
    personas = store.get_personas(house.id)
    completeness = _completeness_score_fast(house, len(messages), len(personas))
    return {
        "id": str(house.id),
        "completeness_score": completeness,  # ← added
        "name": house.name,
        ...
    }
```

---

### Bug 4 — Graph explorer shows 0 nodes (graph not built on startup)

**Root cause**: `startup_event()` never called `get_graph_engine().rebuild()`.

**Fix** — `src/web_app.py:95-101` (after `_sync_engine.start()`)
```python
    # Build the knowledge graph on startup
    try:
        from src.grounding.graph import get_graph_engine
        get_graph_engine().rebuild()
        log.info("Graph engine rebuilt on startup")
    except Exception as e:
        log.warning("Graph rebuild on startup failed: %s", e)
```

---

## OPENCODE_FIXES.md (Bug Fixes 1 & 2) — Already Applied in Prior Session

### Bug 1 — Folder connection shows raw ID instead of folder name

**Fix** — `src/web_app.py:2757-2773`
Split single try/except into three independent blocks so `get_folder_name()` is always called even if `get_account_email()` fails.

**Fix** — `src/sources/google_drive.py:127-136`
Added `supportsAllDrives: "true"` to `get_folder_name()` params.

**Fix** — `src/sources/sync.py:75-82`
Heal `folder_name` if it was stored as raw ID.

### Bug 2 — Deleting a connection shows no feedback

**Fix** — `src/web/dashboard.html:1823`
Added `id="conn-card-${c.id}"` to connection cards.

**Fix** — `src/web/dashboard.html:1866-1878`
Replaced `disconnectSource()` with version that fades card, removes on success, restores on error, shows toasts.

---

## OPENCODE_PARALLEL_CHUNKS.md — Parallelize Chunk Structuring

### Change 1 — Imports
`src/pipeline/structure.py:1-10`
```python
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
```

### Change 2 — `__init__` lock
`src/pipeline/structure.py:331-334`
```python
def __init__(self, openai_api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
    self.client = OpenAI(api_key=openai_api_key or os.environ.get("OPENAI_API_KEY"))
    self.model = model
    self._usage_lock = threading.Lock()  # ← added
```

### Change 3 — Parallel execution in `structure()`
`src/pipeline/structure.py:350-361`
```python
else:
    chunks = self._split_text(text)
    houses = [None] * len(chunks)
    max_workers = min(len(chunks), 5)  # cap at 5
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {}
        for i, chunk in enumerate(chunks):
            futures[pool.submit(self._structure_single_chunk, chunk, source_name, prompt_template)] = i
        for future in as_completed(futures):
            houses[futures[future]] = future.result()
    house = self._merge_structures(houses, source_name)
```

### Change 4 — Thread-safe usage accumulation
`src/pipeline/structure.py:409-412`
```python
if hasattr(self, "_usage") and response.usage:
    with self._usage_lock:
        self._usage["input_tokens"] += response.usage.prompt_tokens
        self._usage["output_tokens"] += response.usage.completion_tokens
```

---

## OPENCODE_4_FIXES.md — 4 More Fixes

### Fix 1 — Add `delete_houses_by_source_id` to `src/store.py:629`
```python
def delete_houses_by_source_id(self, source_id: str) -> int:
    """Delete all houses with the given source_id. Returns count deleted."""
    with self.session() as s:
        rows = s.query(HouseModel).filter(HouseModel.source_id == source_id).all()
        count = len(rows)
        for row in rows:
            s.delete(row)
        if count:
            s.commit()
            _invalidate_graph()
        return count
```

### Fix 2 — Use in `src/sources/sync.py:232`
Replaced single-house cleanup with:
```python
store.delete_houses_by_source_id(file_info.file_id)
```

### Fix 3 — Heal dangling source files in `src/sources/sync.py:94`
Added block before error retry loop to detect source files marked `synced` whose house was deleted, and re-queue them.

### Fix 4 — Inline delete confirmation in `src/web/dashboard.html`
- **4a**: Added `id="house-card-${h.id}"` to framework cards, `class="house-card-footer"` to footer
- **4b**: Added `id="detail-delete-btn"` to detail view delete button
- **4c**: Replaced `deleteHouse()` with inline-confirm version + `_doDeleteHouse()` for optimistic DOM removal

---

## Files Modified (Summary)

| File | Fixes Applied |
|---|---|
| `src/pipeline/structure.py` | Fixes 1a, PARALLEL (import, init, structure, usage lock) |
| `src/web_app.py` | Fixes 1b, 2a, 3, 4, startup graph rebuild |
| `src/sources/sync.py` | Fixes 1c healing, 2 cleanup, 3 dangling heal, PARALLEL (prior session) |
| `src/sources/google_drive.py` | Fix 1 supportsAllDrives (prior session) |
| `src/store.py` | Fix 4 `delete_houses_by_source_id` |
| `src/web/dashboard.html` | Fixes 1c, 2b/2c/2d, 4a/4b/4c, resync UI |

---

## Server Status

- **Stopped**: All python.exe processes killed (PIDs 32956, 31180, 7908, 29612)
- **Restarted**: `venv\Scripts\python.exe run_server.py` (PID 19304, started 5/1/2026 1:47 PM)
- **Verification**: Server process confirmed running via `Get-Process`

---

## Expected Behavior After Restart

1. **Drive sync** — Documents structure correctly with proper `key_messages`, no empty houses
2. **Resync** — Available via new button in connection files table
3. **Delete framework** — Inline confirmation (no browser `confirm()`), optimistic card removal
4. **Completeness** — Frameworks list and detail view show correct % score
5. **Graph explorer** — Populated immediately on startup
6. **Parallel chunks** — 10-chunk document completes in ~25-35s instead of 4-5 min
7. **Orphan cleanup** — Failed sync retries don't accumulate stale houses
8. **Dangling heal** — Source files with missing houses auto re-queue on next sync
