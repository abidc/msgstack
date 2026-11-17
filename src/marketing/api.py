"""Thin REST surface over src/marketing/tools.py.

The strategy doc's point about MCP-only being a liability is that an owner
needs somewhere to *see* the queue and the log. This router is the minimum
that a thin UI (or n8n, or a curl) can drive. It is mounted by web_app.py
under ``/api/marketing`` and shares the brand-scoped behaviour of the tools.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import tools
from .store import NotFound

router = APIRouter(prefix="/api/marketing", tags=["marketing"])


def _run(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class IntakeBody(BaseModel):
    name: str
    one_liner: str = ""
    audience: str = ""
    tone: list[str] = Field(default_factory=list)
    we_say: list[str] = Field(default_factory=list)
    we_never_say: list[str] = Field(default_factory=list)
    locked_claims: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    off_limits: list[str] = Field(default_factory=list)
    cta: str = ""
    example_posts: list[str] = Field(default_factory=list)
    owner: str = ""
    kind: str = "solo"
    workspace_id: str = "default"
    weekly_quota: dict = Field(default_factory=dict)


class CanonPatch(BaseModel):
    one_liner: Optional[str] = None
    audience: Optional[str] = None
    tone: Optional[list[str]] = None
    we_say: Optional[list[str]] = None
    we_never_say: Optional[list[str]] = None
    locked_claims: Optional[list[str]] = None
    topics: Optional[list[str]] = None
    off_limits: Optional[list[str]] = None
    cta: Optional[str] = None
    example_posts: Optional[list[str]] = None
    max_words: Optional[dict] = None
    allow_first_person_experience: Optional[bool] = None
    notes: Optional[str] = None


class CheckBody(BaseModel):
    text: str
    channel: str = "linkedin"
    kind: str = "post"
    source_text: str = ""


class GenerateBody(BaseModel):
    channel: str = "linkedin"
    start_date: Optional[str] = None
    count: int = 3
    brief: str = ""
    topics: Optional[list[str]] = None
    use_llm: Optional[bool] = None


class ApproveBody(BaseModel):
    decided_by: str = ""
    publish_at: Optional[str] = None
    destination: str = "manual"
    reason: str = ""
    override: bool = False
    edited_body: Optional[str] = None


class RejectBody(BaseModel):
    reason: str
    decided_by: str = ""


class PublishedBody(BaseModel):
    external_ref: str = ""
    published_at: Optional[str] = None
    metrics: dict = Field(default_factory=dict)


@router.post("/brands")
def create_brand(body: IntakeBody):
    return _run(tools.brand_intake, **body.model_dump())


@router.get("/brands")
def list_brands(workspace_id: Optional[str] = None):
    return _run(tools.list_brands, workspace_id)


@router.get("/brands/{brand_id}")
def get_brand(brand_id: str):
    return _run(tools.get_brand, brand_id)


@router.patch("/brands/{brand_id}/canon")
def patch_canon(brand_id: str, body: CanonPatch):
    return _run(tools.update_voice_canon, brand_id, **body.model_dump(exclude_none=True))


@router.post("/brands/{brand_id}/check")
def check(brand_id: str, body: CheckBody):
    return _run(tools.check_voice, brand_id, **body.model_dump())


@router.post("/brands/{brand_id}/generate")
def generate(brand_id: str, body: GenerateBody):
    return _run(tools.generate_week, brand_id, **body.model_dump())


@router.get("/brands/{brand_id}/queue")
def queue(brand_id: str, status: Optional[str] = "open", channel: Optional[str] = None):
    return _run(tools.review_queue, brand_id, status=status, channel=channel)


@router.post("/brands/{brand_id}/content/{content_id}/approve")
def approve(brand_id: str, content_id: str, body: ApproveBody):
    return _run(tools.approve_content, brand_id, content_id, **body.model_dump())


@router.post("/brands/{brand_id}/content/{content_id}/reject")
def reject(brand_id: str, content_id: str, body: RejectBody):
    return _run(tools.reject_content, brand_id, content_id, **body.model_dump())


@router.post("/brands/{brand_id}/content/{content_id}/published")
def published(brand_id: str, content_id: str, body: PublishedBody):
    return _run(tools.mark_published, brand_id, content_id, **body.model_dump())


@router.get("/brands/{brand_id}/results")
def results(brand_id: str, since: Optional[str] = None):
    return _run(tools.get_results, brand_id, since=since)
