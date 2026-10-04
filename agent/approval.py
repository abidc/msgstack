"""Approve action -> MsgStack's existing review-log REST endpoint.

There is currently no MCP tool for writing review actions (the whole MCP
tool surface in src/server.py is read/generate-only), so this goes over
HTTP to the admin app's existing endpoint rather than inventing a parallel
write path or adding a new MCP tool (which would touch src/server.py, where
a parallel workstream is already making changes).

Scope note: MsgStack's review log (src/store.py ReviewLogModel) is
domain-level, not a per-entry approval gate, and the existing endpoint
(src/web_app.py mark_house_reviewed) takes no custom note — it always logs
a fixed "marked as reviewed" message server-side. "Approve" here logs a
review action against the domain the draft was grounded in; it is not a
finer-grained per-entry approval system, because one doesn't exist yet to
call into, and it can't carry which specific draft was approved beyond
what the domain-level log already records.
"""

from __future__ import annotations

from agent.config import settings

try:
    import httpx2 as _httpx
except ImportError:
    import httpx as _httpx


async def log_approval(domain_id: str, performed_by: str) -> dict:
    auth = None
    if settings.msgstack_basic_user:
        auth = (settings.msgstack_basic_user, settings.msgstack_basic_pass)
    url = f"{settings.msgstack_base_url}/api/canon-domains/{domain_id}/review"
    async with _httpx.AsyncClient(auth=auth, timeout=30.0) as client:
        resp = await client.post(url, params={"performed_by": performed_by})
        resp.raise_for_status()
        return resp.json()
