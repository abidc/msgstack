"""Data models for MsgStack MCP."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SectionType(str, Enum):
    HEADLINE = "headline"
    SUBHEAD = "subhead"
    BENEFIT = "benefit"
    PROOF_POINT = "proof_point"
    OBJECTION = "objection"
    SOCIAL_PROOF = "social_proof"
    POSITIONING = "positioning"


class Channel(str, Enum):
    ALL = "all"
    LINKEDIN = "linkedin"
    EMAIL = "email"
    LANDING = "landing"
    PAID = "paid"
    TWITTER = "twitter"
    BLOG = "blog"


class HouseStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    NEEDS_REVIEW = "needs_review"


class MessageHouse(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    source: str = "manual"
    source_id: str | None = None
    summary: str = ""
    audience: str = ""
    brand_personality: str = ""
    positioning: str = ""
    tagline: str = ""
    differentiation: str = ""
    status: HouseStatus = HouseStatus.ACTIVE
    last_synced: datetime | None = None

    class Config:
        use_enum_values = True


class KeyMessage(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    message_house_id: UUID
    section_type: SectionType
    priority: int = Field(ge=1, le=5)
    content: str
    variants: dict[str, str] = Field(default_factory=dict)
    personas: list[str] = Field(default_factory=list)
    channels: list[Channel] = Field(default_factory=lambda: [Channel.ALL])
    source_chunk_id: str | None = None

    class Config:
        use_enum_values = True


class Persona(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    message_house_id: UUID
    name: str
    description: str = ""
    pain_points: list[str] = Field(default_factory=list)
    buying_triggers: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)


class GroundingChunk(BaseModel):
    id: str
    message_house_id: UUID
    key_message_id: UUID | None = None
    content: str
    section_type: SectionType
    priority: int
    persona: str | None = None
    channel: Channel = Channel.ALL
    house_name: str = ""
    house_summary: str = ""
    last_synced: datetime | None = None

    class Config:
        use_enum_values = True


class GroundingResult(BaseModel):
    chunk_id: str
    content: str
    section_type: str
    priority: int
    persona: str | None
    channel: str
    channel_variants: dict[str, str] = Field(default_factory=dict)
    source: dict
    confidence: float = Field(ge=0.0, le=1.0)
    rerank_reason: str = ""


class GroundingContext(BaseModel):
    active_house_id: UUID | None = None
    house_name: str = ""
    house_summary: str = ""
    active_personas: list[str] = Field(default_factory=list)
    used_chunks: int = 0
    confidence: str = "medium"
    coverage: dict[str, str] = Field(default_factory=dict)
    gaps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GroundingResponse(BaseModel):
    results: list[GroundingResult]
    grounding_context: GroundingContext


class SearchFilters(BaseModel):
    section_types: list[str] | None = None
    personas: list[str] | None = None
    channels: list[str] | None = None
    message_houses: list[str] | None = None
    include_variants: bool = True
    min_priority: int | None = None