# OpenCode Instructions — 4 Fixes

---

## Overview

Four issues to fix across three files:

1. **Orphaned houses** — failed sync retries create stale partial houses; root-cause fix never applied
2. **Dangling house detection** — source files marked `synced` whose house was deleted externally never re-sync
3. **Inline delete confirmation** — framework delete button uses a browser `confirm()` popup; replace with inline UX
4. **Immediate card removal** — after delete, the framework card stays on screen until manual browser refresh

Files changed: `src/store.py`, `src/sources/sync.py`, `src/web/dashboard.html`

---

## Fix 1 — Add `delete_houses_by_source_id` to `src/store.py`

**Location**: `src/store.py`, right after the `delete_house` method (around line 627).

The `delete_house` method ends at `return False`. Add the new method immediately after it:

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

**Why**: When a sync fails partway through (e.g. Pinecone step fails after the house is written to DB), the partially-created house is orphaned. Multiple retries compound this. The existing cleanup only deletes the single house_id recorded in the source_file row — but if the failure happened before that row was updated, older orphans accumulate. This method deletes ALL houses sharing the same `source_id` (which equals `file_info.file_id` for Drive files), covering orphans from all prior failed attempts.

---

## Fix 2 — Use `delete_houses_by_source_id` in `src/sources/sync.py`

**Location**: `src/sources/sync.py`, inside `_ingest_file`, around lines 207–213.

**Replace** this existing pre-commit cleanup block:

```python
        # Check if a house already exists for this Drive file; if so, delete and recreate
        existing = self.store.get_source_file_by_drive_id(conn["id"], file_info.file_id)
        if existing and existing.get("house_id"):
            try:
                store.delete_house(existing["house_id"])
            except Exception:
                pass
```

**With**:

```python
        # Delete all houses previously created for this Drive file (including orphans
        # from failed retries that were never linked back to the source_file record).
        store.delete_houses_by_source_id(file_info.file_id)
```

**Why**: The old code only deleted one house (the one tracked in source_file.house_id). If the failure happened before source_file was updated with the new house_id, orphaned houses from earlier attempts were never cleaned up. The new call deletes everything with `source_id = file_info.file_id` unconditionally, regardless of whether source_file is tracking it.

---

## Fix 3 — Heal dangling source files in `src/sources/sync.py`

**Location**: `src/sources/sync.py`, inside `sync_connection`, in the `try:` block — add this block **immediately before** the `# Retry any files still in error state` comment (around line 95).

**Add the following block** between the "process changed files" loop and the error retry loop:

```python
            # Heal source files whose house was deleted externally (e.g. via the UI or a
            # previous orphan cleanup). Re-queue them so the error retry loop below re-ingests.
            from src.store import get_store as _get_store
            _live_store = _get_store()
            for _sf in self.store.list_source_files(connection_id):
                if _sf.get("sync_status") == "synced" and _sf.get("house_id"):
                    try:
                        _house = _live_store.get_house(_sf["house_id"])
                    except Exception:
                        _house = None
                    if not _house:
                        log.info(
                            "House %s missing for source file %s — re-queuing for re-ingest",
                            _sf["house_id"], _sf["file_name"],
                        )
                        self.store.upsert_source_file(
                            connection_id=connection_id,
                            drive_file_id=_sf["drive_file_id"],
                            file_name=_sf["file_name"],
                            mime_type=_sf["mime_type"],
                            drive_modified_at=_sf.get("drive_modified_at", ""),
                            sync_status="error",
                            error_message="house missing, re-queued for re-ingest",
                        )
```

**Why**: A source file can be `synced` while its linked house no longer exists — for example, if a user deleted the house via the UI, or if the orphan cleanup in Fix 1 deleted a house that was being tracked by a source_file row. Without this check, those source files stay `synced` forever and never re-sync. By re-queuing them as `error` before the error retry loop runs, they get re-ingested in the same sync cycle.

**Note on `get_house` signature**: The method accepts either a UUID or a string representation of a UUID. `_sf["house_id"]` is already a string (stored as `str(house.id)`). Pass it directly; the store handles the conversion.

---

## Fix 4 — Inline delete confirmation in `src/web/dashboard.html`

Three sub-changes in the same file.

### 4a — Add `id` attribute to framework cards in `loadHouses()`

**Location**: around line 615 in `loadHouses()`.

**Replace** the card opening tag:

```javascript
                <div class="card" style="cursor:pointer;transition:border-color .12s;"
                     onmouseenter="this.style.borderColor='var(--primary)'" onmouseleave="this.style.borderColor=''"
                     onclick="viewHouse('${h.id}')">
```

**With** (adds `id` and `data-house-id` so the delete handler can find the card by ID):

```javascript
                <div class="card" id="house-card-${h.id}" style="cursor:pointer;transition:border-color .12s;"
                     onmouseenter="this.style.borderColor='var(--primary)'" onmouseleave="this.style.borderColor=''"
                     onclick="viewHouse('${h.id}')">
```

Also add `class="house-card-footer"` to the footer stats row so it can be targeted for inline replacement. **Replace** the footer div opening:

```javascript
                    <div style="display:flex;gap:12px;font-size:11px;color:var(--text-3);font-weight:500;text-transform:uppercase;letter-spacing:.04em;align-items:center;">
                        <span>${h.message_count} Messages</span>
                        <span>${h.persona_count} Personas</span>
                        <span style="margin-left:auto;color:${h.completeness_score>=75?'var(--success)':h.completeness_score>=50?'var(--warn)':'var(--text-3)'};">${h.completeness_score}%</span>
                        <button class="btn btn-ghost btn-sm" style="font-size:10px;padding:2px 7px;color:var(--danger);" onclick="event.stopPropagation();deleteHouse('${h.id}')">Delete</button>
                    </div>
```

**With**:

```javascript
                    <div class="house-card-footer" style="display:flex;gap:12px;font-size:11px;color:var(--text-3);font-weight:500;text-transform:uppercase;letter-spacing:.04em;align-items:center;">
                        <span>${h.message_count} Messages</span>
                        <span>${h.persona_count} Personas</span>
                        <span style="margin-left:auto;color:${h.completeness_score>=75?'var(--success)':h.completeness_score>=50?'var(--warn)':'var(--text-3)'};">${h.completeness_score}%</span>
                        <button class="btn btn-ghost btn-sm" style="font-size:10px;padding:2px 7px;color:var(--danger);" onclick="event.stopPropagation();deleteHouse('${h.id}')">Delete</button>
                    </div>
```

### 4b — Add `id` to the Delete button in the detail view

**Location**: around line 716 in `_renderHouseDetail()` (the button row inside the detail header).

**Replace**:

```javascript
                <button class="btn btn-ghost btn-sm" style="color:var(--danger);border-color:var(--danger);" onclick="deleteHouse('${house.id}')">Delete</button>
```

**With**:

```javascript
                <button id="detail-delete-btn" class="btn btn-ghost btn-sm" style="color:var(--danger);border-color:var(--danger);" onclick="deleteHouse('${house.id}')">Delete</button>
```

### 4c — Replace `deleteHouse()` function with inline-confirm version

**Location**: around line 1936.

**Replace the entire existing `deleteHouse` function**:

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

**With these three functions**:

```javascript
    function deleteHouse(id) {
        const card = document.getElementById('house-card-' + id);
        if (card) {
            // List view — replace the footer row with inline confirmation
            const footer = card.querySelector('.house-card-footer');
            if (!footer) return;
            footer.innerHTML = `
                <span style="font-size:12px;color:var(--danger);font-weight:600;text-transform:none;letter-spacing:0;">Delete permanently?</span>
                <button class="btn btn-ghost btn-sm" style="color:var(--danger);border-color:var(--danger);font-size:10px;padding:2px 8px;"
                        onclick="event.stopPropagation();_doDeleteHouse('${id}')">Yes, delete</button>
                <button class="btn btn-ghost btn-sm" style="font-size:10px;padding:2px 8px;"
                        onclick="event.stopPropagation();loadHouses()">Cancel</button>`;
        } else {
            // Detail view — show inline confirmation next to the Delete button
            const btn = document.getElementById('detail-delete-btn');
            if (!btn) return;
            btn.style.display = 'none';
            const confirm_span = document.createElement('span');
            confirm_span.id = 'detail-delete-confirm';
            confirm_span.style.cssText = 'display:flex;gap:6px;align-items:center;';
            confirm_span.innerHTML = `
                <span style="font-size:12px;color:var(--danger);font-weight:600;">Delete permanently?</span>
                <button class="btn btn-ghost btn-sm" style="color:var(--danger);border-color:var(--danger);font-size:10px;" onclick="_doDeleteHouse('${id}')">Confirm</button>
                <button class="btn btn-ghost btn-sm" style="font-size:10px;" onclick="document.getElementById('detail-delete-confirm').remove();document.getElementById('detail-delete-btn').style.display='';">Cancel</button>`;
            btn.insertAdjacentElement('afterend', confirm_span);
        }
    }

    async function _doDeleteHouse(id) {
        const card = document.getElementById('house-card-' + id);
        if (card) {
            // Immediately remove from DOM (optimistic update)
            card.remove();
            // If the list is now empty, show the empty state
            const list = document.getElementById('houses-list');
            if (list && !list.querySelector('.card')) {
                list.innerHTML = `<div style="grid-column:1/-1;" class="card"><div style="color:var(--text-3);font-size:14px;text-align:center;padding:32px 0;">No frameworks yet. <button class="btn btn-ghost btn-sm" onclick="showSection(\'upload\')">Upload a document →</button></div></div>`;
            }
        }
        try {
            await apiFetch(`${API}/houses/${id}`, {method: 'DELETE'});
            showToast('Framework deleted', 'success');
            if (!card) showSection('frameworks');
        } catch(e) {
            showToast('Delete failed: ' + e.message, 'error');
            loadHouses(); // Restore list on failure (re-fetches from server)
        }
    }
```

**Why**: The original `confirm()` is a blocking browser dialog that looks jarring. The new flow replaces the card's footer row with "Delete permanently? / Yes, delete / Cancel" inline — no dialog, no page leave. The card is removed from the DOM immediately on confirm (optimistic) so the user sees instant feedback, and if the API call fails, `loadHouses()` restores the list from the server.

---

## After applying all changes

Restart the server:
```
cd C:\Users\Abid\msgstack-mcp
venv\Scripts\python.exe run_server.py
```

The next background sync cycle (within 5 minutes, or triggered by the server restart) will:
1. Detect any source files with `sync_status="synced"` whose house no longer exists (Fix 3)
2. Re-queue them as `error`
3. Re-ingest them using `_ingest_file` which now correctly clears all prior orphaned houses first (Fixes 1+2)

No manual resync needed — it happens automatically on the next poll.
