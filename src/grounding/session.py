"""In-memory session tracking for grounding context across a conversation."""

import time
from typing import Optional
from uuid import UUID

from src.models import GroundingContext, GroundingResult

_SESSION_TTL_SECONDS = 1800  # 30 minutes


class Session:
    def __init__(self):
        self.active_spec_id: Optional[UUID] = None
        self.active_spec_name: str = ""
        self.active_spec_summary: str = ""
        self.active_personas: list[str] = []
        self.active_workspace_id: str = "default"
        self.recent_searches: list[str] = []
        self.used_chunks: list[str] = []
        self._context = GroundingContext()
        self._created_at: float = time.time()
        self._last_used: float = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self._last_used) > _SESSION_TTL_SECONDS

    def touch(self) -> None:
        self._last_used = time.time()

    def set_active_spec(
        self, spec_id: UUID, spec_name: str, spec_summary: str, personas: list[str], workspace_id: str = "default"
    ) -> GroundingContext:
        self.active_spec_id = spec_id
        self.active_spec_name = spec_name
        self.active_spec_summary = spec_summary
        self.active_personas = personas
        self.active_workspace_id = workspace_id
        self._context = GroundingContext(
            active_spec_id=spec_id,
            spec_name=spec_name,
            spec_summary=spec_summary,
            active_personas=personas,
        )
        return self._context

    def update_from_search(self, results: list[GroundingResult], ctx: GroundingContext) -> None:
        if ctx.active_spec_id and not self.active_spec_id:
            self.active_spec_id = ctx.active_spec_id
            self.active_spec_name = ctx.spec_name
            self.active_spec_summary = ctx.spec_summary

        if ctx.active_personas:
            self.active_personas = list(set(self.active_personas + ctx.active_personas))

        self.used_chunks.extend([r.chunk_id for r in results])

        if results:
            self._context = ctx

    def get_context(self) -> GroundingContext:
        return GroundingContext(
            active_spec_id=self.active_spec_id,
            spec_name=self.active_spec_name,
            spec_summary=self.active_spec_summary,
            active_personas=self.active_personas,
            used_chunks=len(self.used_chunks),
            confidence=self._context.confidence,
            coverage=self._context.coverage,
            gaps=self._context.gaps,
            warnings=self._context.warnings,
        )


_session: Optional[Session] = None


def get_session() -> Session:
    global _session
    if _session is None or _session.is_expired():
        _session = Session()
    _session.touch()
    return _session


def reset_session() -> None:
    global _session
    _session = Session()