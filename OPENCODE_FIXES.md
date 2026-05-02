# OpenCode Fix Instructions — msgstack-mcp

Four bugs to fix in `C:\Users\Abid\msgstack-mcp`. Make all changes, then restart the server.

---

## Bug 1 — Drive-synced frameworks have empty content (name = filename, no messages)

**Root cause**: `StructuredHouse.key_messages` at `src/pipeline/structure.py:51` is declared as a required field with no default. The `_STRUCTURE_PROMPT` asks the LLM to return `pillars` + `ungrouped_chunks` (not a top-level `key_messages`), so when `StructuredHouse(**data)` is called, Pydantic raises `ValidationError` for the missing `key_messages`. This falls through to `_parse_markdown()`, which produces a bare house with only the filename as the name and no messages.

### Fix 1a — Add default to `key_messages` field

**File**: `src/pipeline/structure.py`, line 51

Change:
```python
key_messages: list[dict]
```
To:
```python
key_messages: list[dict] = Field(default_factory=list)
```

The `_commit_structured_house` function in `web_app.py` already handles the pillar-based path correctly at lines 916–924 via `if structured.pillars:` — so once the `StructuredHouse` constructs without error, those chunks will be committed.

### Fix 1b — Add per-file Re-sync endpoint

**File**: `src/web_app.py`

Add this endpoint **after** the existing `GET /api/connections/{connection_id}/files` endpoint (after line 2831):

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
    # Delete the existing house so a fresh one is created on re-ingest
    if sf.get("house_id"):
        try:
            store.delete_house(UUID(sf["house_id"]))
        except Exception:
            pass
    # Reset to error so the error-file retry loop picks it up on next sync
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

Note: `UUID` is already imported at the top of `web_app.py`.

### Fix 1c — Add Re-sync button to connection files table

**File**: `src/web/dashboard.html`

In the `viewConnectionFiles` function (around line 1900), the table row currently has 4 columns: File, Status, Synced, Framework. Add a 5th "Actions" column.

Change the `<thead>` row:
```html
<thead><tr style="color:var(--text-3);text-align:left;">
    <th style="padding:4px 8px;font-weight:500;">File</th>
    <th style="padding:4px 8px;font-weight:500;">Status</th>
    <th style="padding:4px 8px;font-weight:500;">Synced</th>
    <th style="padding:4px 8px;font-weight:500;">Framework</th>
</tr></thead>
```
To:
```html
<thead><tr style="color:var(--text-3);text-align:left;">
    <th style="padding:4px 8px;font-weight:500;">File</th>
    <th style="padding:4px 8px;font-weight:500;">Status</th>
    <th style="padding:4px 8px;font-weight:500;">Synced</th>
    <th style="padding:4px 8px;font-weight:500;">Framework</th>
    <th style="padding:4px 8px;font-weight:500;"></th>
</tr></thead>
```

Change the `return` inside `data.files.map(f => { ... })` to add a Re-sync button cell. The existing row template ends with:
```html
<td style="padding:5px 8px;">${houseLink}</td>
</tr>`;
```
Change it to:
```html
<td style="padding:5px 8px;">${houseLink}</td>
<td style="padding:5px 8px;"><button class="btn btn-ghost btn-sm" style="font-size:11px;padding:2px 8px;" onclick="resyncFile('${connId}','${f.drive_file_id}',this)">Re-sync</button></td>
</tr>`;
```

Add the `resyncFile` JS function somewhere in the `<script>` block (near the other connection functions):
```javascript
async function resyncFile(connId, driveFileId, btn) {
    btn.disabled = true;
    btn.textContent = '…';
    try {
        await apiFetch(`/api/connections/${connId}/source-files/${encodeURIComponent(driveFileId)}/resync`, {method: 'POST'});
        showToast('File queued for re-sync. Trigger a sync or wait for next poll.', 'success');
        // Trigger an immediate sync so user doesn't wait 5 min
        await apiFetch(`/api/connections/${connId}/sync`, {method: 'POST'}).catch(() => {});
        setTimeout(() => viewConnectionFiles(connId), 3000); // Refresh table after a moment
    } catch(e) {
        showToast('Re-sync failed: ' + e.message, 'error');
        btn.disabled = false;
        btn.textContent = 'Re-sync';
    }
}
```

---

## Bug 2 — No way to delete frameworks (missing UI + missing Pinecone cleanup)

### Fix 2a — Update delete endpoint to clean up Pinecone + rebuild graph

**File**: `src/web_app.py`, lines 400–404

Replace the existing `delete_house` endpoint:
```python
@app.delete("/api/houses/{house_id}")
def delete_house(house_id: str):
    if not store.delete_house(UUID(house_id)):
        raise HTTPException(404, "House not found")
    return {"ok": True, "deleted_id": house_id}
```
With:
```python
@app.delete("/api/houses/{house_id}")
def delete_house(house_id: str):
    try:
        uid = UUID(house_id)
    except Exception:
        raise HTTPException(400, "Invalid house ID")
    if not store.delete_house(uid):
        raise HTTPException(404, "House not found")
    # Remove Pinecone vectors for this house
    try:
        from src.grounding.search import GroundingEngine
        ge = GroundingEngine(
            store=store,
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
            index_name=os.environ.get("PINECONE_INDEX", "msgstack-chunks"),
            namespace="default",
        )
        ge.ensure_index()
        ge.index.delete(filter={"message_house_id": house_id}, namespace="default")
    except Exception as exc:
        log.warning("Pinecone cleanup on house delete failed: %s", exc)
    # Rebuild graph so deleted house is removed from graph explorer immediately
    try:
        from src.grounding.graph import get_graph_engine
        get_graph_engine().rebuild()
    except Exception as exc:
        log.warning("Graph rebuild after house delete failed: %s", exc)
    return {"ok": True, "deleted_id": house_id}
```

### Fix 2b — Add `deleteHouse` JS function to dashboard.html

**File**: `src/web/dashboard.html`

Add this function somewhere in the `<script>` block, near the other house-related functions (e.g., after `viewHouse`):
```javascript
async function deleteHouse(id) {
    if (!confirm('Permanently delete this framework and all its messages? This cannot be undone.')) return;
    try {
        await apiFetch(`${API}/houses/${id}`, {method: 'DELETE'});
        showToast('Framework deleted', 'success');
        showSection('frameworks');
        loadHouses();
    } catch(e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
}
```

### Fix 2c — Add Delete button in house detail view

**File**: `src/web/dashboard.html`

In the `_renderHouseDetail` function (around line 711–715), the header button row currently is:
```html
<div style="display:flex;gap:8px;align-items:center;flex-shrink:0;">
    <span style="font-size:12px;font-weight:600;color:${scoreColor};border:1px solid ${scoreColor};padding:3px 10px;border-radius:100px;">${score}% complete</span>
    <button class="btn btn-ghost btn-sm" onclick="viewArtifactForHouse('${house.id}')">Generate →</button>
    <button class="btn btn-ghost btn-sm" onclick="showSection('frameworks')">← Back</button>
</div>
```
Change it to:
```html
<div style="display:flex;gap:8px;align-items:center;flex-shrink:0;">
    <span style="font-size:12px;font-weight:600;color:${scoreColor};border:1px solid ${scoreColor};padding:3px 10px;border-radius:100px;">${score}% complete</span>
    <button class="btn btn-ghost btn-sm" onclick="viewArtifactForHouse('${house.id}')">Generate →</button>
    <button class="btn btn-ghost btn-sm" onclick="showSection('frameworks')">← Back</button>
    <button class="btn btn-ghost btn-sm" style="color:var(--danger);border-color:var(--danger);" onclick="deleteHouse('${house.id}')">Delete</button>
</div>
```

### Fix 2d — Add Delete button to frameworks list cards

**File**: `src/web/dashboard.html`

In the `loadHouses` function (around line 614–628), the card template currently has `onclick="viewHouse('${h.id}')"` on the outer div. Add a delete button inside the card that stops propagation so clicking it doesn't open the detail view.

At the end of the card content, before the closing `</div>` of the card, add a delete icon button. The card currently ends with:
```html
<div style="display:flex;gap:12px;font-size:11px;color:var(--text-3);font-weight:500;text-transform:uppercase;letter-spacing:.04em;">
    <span>${h.message_count} Messages</span>
    <span>${h.persona_count} Personas</span>
    <span style="margin-left:auto;color:${h.completeness_score>=75?'var(--success)':h.completeness_score>=50?'var(--warn)':'var(--text-3)'};">${h.completeness_score}%</span>
</div>
```
Change it to:
```html
<div style="display:flex;gap:12px;font-size:11px;color:var(--text-3);font-weight:500;text-transform:uppercase;letter-spacing:.04em;align-items:center;">
    <span>${h.message_count} Messages</span>
    <span>${h.persona_count} Personas</span>
    <span style="margin-left:auto;color:${h.completeness_score>=75?'var(--success)':h.completeness_score>=50?'var(--warn)':'var(--text-3)'};">${h.completeness_score}%</span>
    <button class="btn btn-ghost btn-sm" style="font-size:10px;padding:2px 7px;color:var(--danger);" onclick="event.stopPropagation();deleteHouse('${h.id}')">Delete</button>
</div>
```

---

## Bug 3 — All frameworks show 0% complete in detail view

**Root cause**: `_house_response()` in `src/web_app.py` (lines 153–192) does not include `completeness_score` in its return dict. The detail view JS does `house.completeness_score || 0`, so it always shows 0%.

### Fix

**File**: `src/web_app.py`, `_house_response()` function (lines 153–192)

The function already fetches `messages` and `personas`. Add the completeness score calculation. Change the return statement to include it:

Find this block (around line 154–156):
```python
def _house_response(house: MessageHouse) -> dict:
    messages = store.get_key_messages(house.id)
    personas = store.get_personas(house.id)
    return {
```
Change to:
```python
def _house_response(house: MessageHouse) -> dict:
    messages = store.get_key_messages(house.id)
    personas = store.get_personas(house.id)
    completeness = _completeness_score_fast(house, len(messages), len(personas))
    return {
```

Then add `"completeness_score": completeness,` to the returned dict, right after `"id": str(house.id),`. The full first few lines of the return dict should look like:
```python
    return {
        "id": str(house.id),
        "completeness_score": completeness,
        "name": house.name,
        ...
    }
```

---

## Bug 4 — Graph explorer shows 0 nodes (graph not built on startup)

**Root cause**: `GraphEngine` starts with `_built = False`. The startup event in `src/web_app.py` (lines 65–93) never calls `get_graph_engine().rebuild()`, so the graph stays empty until either a Drive sync completes or someone manually calls `POST /api/graph/rebuild`.

### Fix

**File**: `src/web_app.py`, `startup_event()` function (around line 92–93)

The function currently ends with:
```python
    # Start the background source sync loop (engine already initialized at module level)
    _sync_engine.start()
```

Add a graph rebuild call after that:
```python
    # Start the background source sync loop (engine already initialized at module level)
    _sync_engine.start()

    # Build the knowledge graph on startup so graph explorer and MCP tools work immediately
    try:
        from src.grounding.graph import get_graph_engine
        get_graph_engine().rebuild()
        log.info("Graph engine rebuilt on startup")
    except Exception as e:
        log.warning("Graph rebuild on startup failed: %s", e)
```

---

## After all changes

1. Restart the server: stop `run_server.py` (Ctrl+C) and re-run `venv\Scripts\python.exe run_server.py` from `C:\Users\Abid\msgstack-mcp\`
2. Open the Connections panel, expand the Google Drive connection, click **View Files**, and use the **Re-sync** button on the `Solution_CBWF_HR Service Delivery_Messaging House_Draft_12.15.25.docx` file.
3. Wait ~10 seconds, then refresh the files table — it should show `synced` with a Framework link.
4. Open the Frameworks list — the imported document should now appear with its real name, message count > 0, and proper completeness score.
5. Open the Graph Explorer — it should show nodes for all frameworks immediately after startup.
