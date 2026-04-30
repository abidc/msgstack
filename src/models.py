"""Data models for MsgStack MCP."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SectionType(str, Enum):
    HEADLINE = "headline"
    SUBHEAD = "subhead"
    BENEFIT = "benefit"
    USE_CASE = "use_case"
    PROOF_POINT = "proof_point"
    OBJECTION = "objection"
    SOCIAL_PROOF = "social_proof"
    POSITIONING = "positioning"
    KNOW_YOUR_MARKET = "know_your_market"
    BRAND_VOICE = "brand_voice"
    STYLE_RULE = "style_rule"
    WORD_LIST = "word_list"
    COMPETITOR_STRENGTH = "competitor_strength"
    COMPETITOR_WEAKNESS = "competitor_weakness"
    COMPETITIVE_RESPONSE = "competitive_response"
    NARRATIVE_PILLAR = "narrative_pillar"
    COMPANY_VALUE = "company_value"
    FOUNDING_STORY = "founding_story"
    PERSONA_DETAIL = "persona_detail"


class DocumentType(str, Enum):
    MESSAGE_HOUSE = "message_house"
    BRAND_GUIDE = "brand_guide"
    COMPETITIVE_BRIEF = "competitive_brief"
    CORP_NARRATIVE = "corp_narrative"
    PERSONA_LIBRARY = "persona_library"


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
    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    name: str
    source: str = "manual"
    source_id: str | None = None
    document_type: DocumentType = DocumentType.MESSAGE_HOUSE
    summary: str = ""
    audience: str = ""
    brand_personality: str = ""
    positioning: str = ""
    tagline: str = ""
    differentiation: str = ""
    status: HouseStatus = HouseStatus.ACTIVE
    last_synced: datetime | None = None


class KeyMessage(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: UUID = Field(default_factory=uuid4)
    message_house_id: UUID
    pillar_id: int | None = None
    section_type: SectionType
    priority: int = Field(ge=1, le=5)
    content: str

    @field_validator('priority', mode='before')
    @classmethod
    def clamp_priority(cls, v):
        try:
            return max(1, min(5, int(v)))
        except (TypeError, ValueError):
            return 3
    variants: dict[str, str] = Field(default_factory=dict)
    personas: list[str] = Field(default_factory=list)
    channels: list[Channel] = Field(default_factory=lambda: [Channel.ALL])
    source_chunk_id: str | None = None


class Pillar(BaseModel):
    id: int
    house_id: str
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


class Persona(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    message_house_id: UUID
    name: str
    description: str = ""
    pain_points: list[str] = Field(default_factory=list)
    buying_triggers: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)


class PainPoint(BaseModel):
    id: int
    persona_id: str
    content: str


class BuyingTrigger(BaseModel):
    id: int
    persona_id: str
    content: str


class Objection(BaseModel):
    id: int
    persona_id: str
    statement: str
    response: str | None = None


class GroundingChunk(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

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


COMPLETE_FRAMEWORK_SPEC = {
    "description": "Definition of a complete MsgStack messaging framework (message house).",
    "house_fields": {
        "name": "Brand or product name",
        "summary": "1-2 sentence product overview",
        "positioning": "Full positioning statement — for [audience] who [need], [product] is [category] that [benefit]. Unlike [alt], [product] [key differentiator].",
        "tagline": "7 words or fewer. Memorable and ownable.",
        "differentiation": "2-3 specific ways this is better than alternatives (not just different).",
        "audience": "Firmographic/demographic definition: role, company size, industry.",
        "brand_personality": "Voice and tone descriptors (e.g. bold, precise, friendly).",
        "status": "active | archived | needs_review",
    },
    "required_section_types": {
        "headline": "Attention-grabbing primary messages. Min 3. Priority 1 = most important.",
        "subhead": "Supporting messages that expand on headlines. Min 3.",
        "benefit": "Specific value props with evidence or metrics. Min 4.",
        "proof_point": "Quantified stats, customer counts, analyst citations. Min 3.",
        "objection": "Common objections with concise counter-messaging. Min 3.",
        "social_proof": "Customer quotes, awards, media mentions, G2/analyst recognition. Min 3.",
        "positioning": "Core positioning message in key-message form. Min 1.",
    },
    "key_message_fields": {
        "content": "The core message in plain language.",
        "priority": "1 (highest) to 5. Top 3 should be the sharpest messages.",
        "personas": "Which personas this message is most relevant for.",
        "channels": "Channels where this message appears. 'all' = universal.",
        "variants": {
            "linkedin": "LinkedIn-optimized version (conversational, 15-20 words max)",
            "email": "Email subject-line or body hook version (40-60 chars)",
            "paid": "Paid ad version (punchy, benefit-first, 10-15 words)",
            "twitter": "Twitter/X version (under 240 chars with punch)",
        },
    },
    "persona_fields": {
        "name": "Role title (e.g. CISO, VP Sales, HR Manager)",
        "description": "Who they are, what they own, what success looks like for them.",
        "pain_points": "3-5 specific frustrations this persona has today.",
        "buying_triggers": "2-4 events or pressures that make them evaluate solutions.",
        "objections": "2-4 reasons they hesitate to buy or switch.",
    },
    "minimum_personas": 2,
    "completeness_checklist": [
        "All 7 section types have at least 1 key message",
        "headline, subhead, benefit, proof_point have 3+ messages each",
        "At least 2 personas defined with all fields",
        "All key messages have linkedin and email variants",
        "Positioning statement is a full sentence (50+ chars)",
        "Tagline is present and under 60 chars",
        "Differentiation is specific and comparative (not generic)",
    ],
}


class SearchFilters(BaseModel):
    section_types: list[str] | None = None
    personas: list[str] | None = None
    channels: list[str] | None = None
    message_houses: list[str] | None = None
    include_variants: bool = True
    min_priority: int | None = None
    min_confidence: float | None = None
