"""MsgStack marketing slice — brand voice canon, gated drafts, approval queue, schedule, results.

This package is the thin vertical slice behind docs/STRATEGY_V3_MARKETING_OS.md and
docs/MVP_SPEC.md. It is deliberately self-contained: its own Pydantic models
(`models.py`), its own SQLAlchemy tables prefixed ``mkt_`` (`store.py`), a
deterministic voice gate (`voice_gate.py`), a week-of-drafts generator
(`generator.py`) and the tool functions the MCP server and REST router expose
(`tools.py`, `api.py`). Every tool takes a ``brand_id``; the brand is the tenant.
"""
