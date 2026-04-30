# Task: v0.7 Admin UI — OpenCode

**Project:** MsgStack MCP Server  
**Location:** `C:\Users\Abid\msgstack-mcp\`  
**Goal:** Add four UI features to the admin dashboard: document type selector on upload, channels management page, persona/channel relationship indicators on message cards, and a graph status widget.

---

## Context

The admin UI is a single-file Jinja2 template at `src/web/index.html` (vanilla JS + inline CSS, ~2,300 lines, no build step). The server runs at `http://localhost:8001` (Docker bridge) or `https://mcp.abidc.dev` (production). The current UI has sections: Dashboard, Frameworks, Upload, Artifact Generator, Skills.

Before making any changes, read `src/web/index.html` fully to understand the existing patterns:
- How sections are shown/hidden (look for `showSection()` or similar)
- How the API is called (look for `fetch('/api/...')` patterns)
- How cards/items are rendered (look for template literals building HTML strings)
- The CSS variable system and color scheme

---

## API Contract

These endpoints will exist after the backend work is done. Build the UI against this contract.

### Channels API

```
GET  /api/channels
Response: [{ "id": "email", "name": "Email", "description": "...", "is_default": true }, ...]

POST /api/channels
Body: { "id": "partner_portal", "name": "Partner Portal", "description": "..." }
Response: { "id": "...", "name": "...", "description": "...", "is_default": false }

PATCH /api/channels/{id}
Body: { "name": "...", "description": "..." }
Response: updated channel object

DELETE /api/channels/{id}
Response: { "deleted": true }
Note: Deleting a default channel returns 400 { "detail": "Cannot delete a default channel" }
```

### Document Type (on Upload)

```
POST /api/extract  (existing endpoint — adding optional body field)
Body (multipart/form-data):
  - file: <file>
  - document_type: "message_house" | "brand_guide" | "competitive_brief" | "corp_narrative" | "persona_library"

The extracted and structured house will have document_type set accordingly.
```

### Graph Stats API

```
GET /api/graph/stats
Response: {
  "nodes": 142,
  "edges": 387,
  "by_type": {
    "GroundingDocument": 5,
    "GroundingChunk": 112,
    "Persona": 18,
    "Channel": 7
  }
}

POST /api/graph/rebuild
Response: { "rebuilt": true, "stats": { ...same as above... } }
```

### Houses API (existing — now includes document_type)

```
GET /api/houses
Response: [{ "id": "...", "name": "...", "document_type": "message_house", ... }, ...]
```

---

## Feature 1: Document Type Selector on Upload

**Where:** In the Upload section, before (or alongside) the file drag-drop area.

**Implementation:**

Add a `<select>` element for document type with these options:

```html
<select id="uploadDocType">
  <option value="message_house" selected>Message House</option>
  <option value="brand_guide">Brand Guide</option>
  <option value="competitive_brief">Competitive Brief</option>
  <option value="corp_narrative">Corporate Narrative</option>
  <option value="persona_library">Persona Library</option>
</select>
```

Style to match the existing input/form elements (inherit the dark theme variables).

When the upload is submitted, include the selected value as `document_type` in the FormData:

```javascript
const formData = new FormData();
formData.append('file', selectedFile);
formData.append('document_type', document.getElementById('uploadDocType').value);
```

Add a helper text below the select: *"The document type determines how the AI structures the content."*

---

## Feature 2: Channels Management Page

**Where:** Add a new nav section "Channels" between "Skills" and whatever is currently last. Use the same sidebar nav pattern as existing sections.

**Implementation:**

The Channels section should render:

1. **Channels list** — a card grid (or table) showing all channels. Each row/card shows:
   - Channel `name` and `id`
   - `description` (editable inline)
   - A badge showing "Default" if `is_default: true`
   - Edit and Delete buttons (Delete disabled/greyed for defaults)

2. **Add Channel form** — below the list, a small form:
   ```
   ID:          [text input — slug format, e.g. "partner_portal"]
   Name:        [text input — display name, e.g. "Partner Portal"]
   Description: [text input — optional]
   [Add Channel button]
   ```

3. **On load:** `GET /api/channels` → render the list

4. **On Add:** `POST /api/channels` → refresh list on success

5. **On Delete:** `DELETE /api/channels/{id}` → remove from list; show inline error if 400 (default channel)

6. **On Edit description:** `PATCH /api/channels/{id}` → update in place

Use the same card/list styling as the Skills section for consistency.

---

## Feature 3: Document Type Badge on Framework Cards

**Where:** In the Frameworks list, each framework card/row already shows the house name. Add a small badge showing the `document_type`.

**Implementation:**

Add a badge next to the framework name in the list rendering code. Look for where framework names are rendered in the Frameworks section and add:

```javascript
const docTypeLabel = {
  'message_house': 'Message House',
  'brand_guide': 'Brand Guide',
  'competitive_brief': 'Competitive Brief',
  'corp_narrative': 'Corp Narrative',
  'persona_library': 'Persona Library'
}[house.document_type] || house.document_type;

const badge = `<span class="doc-type-badge doc-type-${house.document_type}">${docTypeLabel}</span>`;
```

Add CSS for the badge variants. Use the existing CSS variable system. Suggested color coding:
- `message_house` — existing accent color (blue/teal)
- `brand_guide` — purple
- `competitive_brief` — orange
- `corp_narrative` — green
- `persona_library` — yellow

```css
.doc-type-badge {
  display: inline-block;
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 10px;
  font-weight: 600;
  letter-spacing: 0.3px;
  margin-left: 8px;
  vertical-align: middle;
}
.doc-type-message_house { background: rgba(var(--accent-rgb), 0.15); color: var(--accent); }
.doc-type-brand_guide { background: rgba(139, 92, 246, 0.15); color: #a78bfa; }
.doc-type-competitive_brief { background: rgba(249, 115, 22, 0.15); color: #fb923c; }
.doc-type-corp_narrative { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
.doc-type-persona_library { background: rgba(234, 179, 8, 0.15); color: #facc15; }
```

---

## Feature 4: Graph Status Widget on Dashboard

**Where:** The Dashboard section shows stats cards (frameworks count, messages count, etc.). Add a new "Knowledge Graph" stat card.

**Implementation:**

On dashboard load, make an additional fetch call:

```javascript
fetch('/api/graph/stats')
  .then(r => r.json())
  .then(data => renderGraphWidget(data))
  .catch(() => renderGraphWidget(null));  // widget shows "Not built" gracefully
```

The widget should display:
- Total nodes count (large number, like the other stat cards)
- Edge count as secondary stat
- A breakdown by type: `Documents: N · Chunks: N · Personas: N · Channels: N`
- A "Rebuild Graph" button that calls `POST /api/graph/rebuild` and refreshes the widget

Example card layout:
```
┌─────────────────────────────┐
│  Knowledge Graph            │
│  142 nodes  ·  387 edges    │
│  Docs: 5 · Chunks: 112      │
│  Personas: 18 · Channels: 7 │
│  [Rebuild Graph]            │
└─────────────────────────────┘
```

Style: match the existing stat cards. The rebuild button should be small and ghost-styled (not a full primary button).

---

## Notes

- The UI runs inside the Docker container. After any edit to `src/web/index.html`, run `docker compose build && docker compose up -d` to pick up the change (or use a volume mount if available for faster iteration).
- Confirm `http://localhost:8001` is live before testing.
- If the backend endpoints (`/api/channels`, `/api/graph/stats`) are not yet implemented, stub the fetch calls with mock data so UI development can proceed in parallel.
- Do NOT modify `src/web/base.html` or `src/web/dashboard.html` (Jinja2 templates) — those are for the admin UI navigation shell; changes to the SPA logic belong in `src/web/index.html`.
