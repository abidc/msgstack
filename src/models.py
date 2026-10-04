"""Data models for MsgStack MCP."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, AliasChoices


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
    SOURCE_MARKDOWN = "source_markdown"
    # Engineering Spec grounding type — not reused from message_house types,
    # since "benefit"/"proof_point" don't mean anything for an API contract.
    API_CONTRACT = "api_contract"
    SLA_COMMITMENT = "sla_commitment"
    VERSIONING_POLICY = "versioning_policy"
    DEPRECATION_NOTICE = "deprecation_notice"
    SECURITY_REQUIREMENT = "security_requirement"
    # Policy Shield grounding type — legal/compliance claims, always Tier 1
    # in practice (see GROUNDING_TYPE_SECTION_TYPES below), never paraphrased.
    LEGAL_DISCLAIMER = "legal_disclaimer"
    PRIVACY_RULE = "privacy_rule"
    COMPLIANCE_ASSERTION = "compliance_assertion"
    COMPLIANCE_RESPONSE = "compliance_response"


class GroundingType(str, Enum):
    MESSAGE_HOUSE = "message_house"  # Product Marketing grounding type
    BRAND_GUIDE = "brand_guide"
    COMPETITIVE_BRIEF = "competitive_brief"
    CORP_NARRATIVE = "corp_narrative"
    PERSONA_LIBRARY = "persona_library"
    # Restored from the August "TERMINAL" detour: the real engineering-shaped
    # grounding types it built, now layered alongside Message House rather
    # than replacing it, per the original v1.0 roadmap framing.
    ENGINEERING_SPEC = "engineering_spec"
    POLICY_SHIELD = "policy_shield"


DocumentType = GroundingType  # Deprecated alias


DEPARTMENT_PRIMARY_GROUNDING = {
    "Product Marketing": GroundingType.MESSAGE_HOUSE,
    "Company Marketing": GroundingType.CORP_NARRATIVE,
    "Enablement": GroundingType.PERSONA_LIBRARY,
    "Product Management": GroundingType.COMPETITIVE_BRIEF,
    "Engineering": GroundingType.ENGINEERING_SPEC,
    "Legal": GroundingType.POLICY_SHIELD,
}


#: Which SectionType values make sense for a domain of a given GroundingType.
#: Soft validation only (see pipeline/conflict.py check_grounding_type_mismatch) —
#: flags a likely-wrong section_type for human review rather than rejecting it
#: outright, consistent with how ingestion conflicts are already handled.
#: GroundingTypes not listed here (brand_guide, corp_narrative, persona_library)
#: have no dedicated vocabulary yet and accept any SectionType.
GROUNDING_TYPE_SECTION_TYPES: dict[GroundingType, set[SectionType]] = {
    GroundingType.MESSAGE_HOUSE: {
        SectionType.HEADLINE, SectionType.SUBHEAD, SectionType.BENEFIT, SectionType.USE_CASE,
        SectionType.PROOF_POINT, SectionType.OBJECTION, SectionType.SOCIAL_PROOF, SectionType.POSITIONING,
        SectionType.KNOW_YOUR_MARKET, SectionType.BRAND_VOICE, SectionType.STYLE_RULE, SectionType.WORD_LIST,
        SectionType.NARRATIVE_PILLAR, SectionType.COMPANY_VALUE, SectionType.FOUNDING_STORY,
        SectionType.PERSONA_DETAIL, SectionType.SOURCE_MARKDOWN,
    },
    GroundingType.COMPETITIVE_BRIEF: {
        SectionType.COMPETITOR_STRENGTH, SectionType.COMPETITOR_WEAKNESS, SectionType.COMPETITIVE_RESPONSE,
        SectionType.POSITIONING, SectionType.SOURCE_MARKDOWN,
    },
    GroundingType.ENGINEERING_SPEC: {
        SectionType.API_CONTRACT, SectionType.SLA_COMMITMENT, SectionType.VERSIONING_POLICY,
        SectionType.DEPRECATION_NOTICE, SectionType.SECURITY_REQUIREMENT, SectionType.SOURCE_MARKDOWN,
    },
    GroundingType.POLICY_SHIELD: {
        SectionType.LEGAL_DISCLAIMER, SectionType.PRIVACY_RULE, SectionType.COMPLIANCE_ASSERTION,
        SectionType.COMPLIANCE_RESPONSE, SectionType.SOURCE_MARKDOWN,
    },
}


#: Historical gen-3 (engineering-era) assertion_type values -> SectionType.
#: Applied once at migration, reversing the August pivot. These two
#: vocabularies are not 1:1 — several engineering types collapse onto the
#: same section type below — so this is a best-effort bucket, not a precise
#: inverse. Nothing is dropped silently; unmapped values land on POSITIONING
#: and get flagged for human re-triage. In practice no real PMM data rides
#: on this path: the only rows on the engineering schema are the fictional
#: demo corpus being discarded in the seed-data restore (see seed_data/seed.py).
LEGACY_ASSERTION_TYPE_MAP: dict[str, str] = {
    "source_markdown": SectionType.SOURCE_MARKDOWN.value,
    "positioning": SectionType.POSITIONING.value,
    "limitation": SectionType.OBJECTION.value,
    "capability": SectionType.BENEFIT.value,
}


#: Historical gen-3 schema_type values -> GroundingType. Same caveat as
#: LEGACY_ASSERTION_TYPE_MAP above: best-effort, not precise, nothing dropped.
LEGACY_SCHEMA_TYPE_MAP: dict[str, str] = {
    "engineering_spec": GroundingType.ENGINEERING_SPEC.value,
    "policy_shield": GroundingType.POLICY_SHIELD.value,
    "service_catalog": GroundingType.PERSONA_LIBRARY.value,
    "incident_record": GroundingType.COMPETITIVE_BRIEF.value,
}


class Channel(str, Enum):
    """Enum kept for backward compatibility; channel IDs used in Pydantic layer."""
    ALL = "all"
    LINKEDIN = "linkedin"
    EMAIL = "email"
    LANDING = "landing"
    PAID = "paid"
    TWITTER = "twitter"
    BLOG = "blog"


class DomainStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    NEEDS_REVIEW = "needs_review"


HouseStatus = DomainStatus  # Deprecated alias


class EntryStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    OUTDATED = "outdated"
    LOCKED = "locked"


MessageStatus = EntryStatus  # Deprecated alias


class ContentTier(str, Enum):
    TIER_1_LOCKED = "tier_1_locked"
    TIER_2_STRUCTURED = "tier_2_structured"
    TIER_3_GROUNDED = "tier_3_grounded"


class ArtifactStatus(str, Enum):
    DRAFT = "draft"
    INTERNAL_REVIEW = "internal_review"
    APPROVED = "approved"


class UserRole(str, Enum):
    OWNER = "owner"
    COLLABORATOR = "collaborator"
    SUGGESTER = "suggester"
    VIEWER = "viewer"


class InheritancePolicy(str, Enum):
    FULL = "full"
    SELECTIVE_OVERRIDE = "selective_override"
    VOCAB_CONSTRAINED = "vocab_constrained"
    AUTONOMOUS = "autonomous"


class NodeType(str, Enum):
    """Node kinds an edge may connect.

    Retained from the August detour's real graph engine (built under the
    engineering-only vocabulary as NodeType.SPEC/ASSERTION); values renamed
    to match the restored Canon Domain/Entry vocabulary.
    """
    CANON_ENTRY = "canon_entry"
    CANON_DOMAIN = "canon_domain"
    ENTITY = "entity"


class RelType(str, Enum):
    """Typed graph relationships.

    DEPENDS_ON and INFORMS are the propagation-bearing edges: a change to the
    destination marks the source stale. The rest are navigational. Positioning-
    neutral — unchanged from the August detour.
    """
    DEPENDS_ON = "DEPENDS_ON"      # src is invalidated when dst changes
    INFORMS = "INFORMS"            # dst feeds src; softer than DEPENDS_ON
    SUPERSEDES = "SUPERSEDES"      # src replaces dst
    CONTRADICTS = "CONTRADICTS"    # src and dst cannot both hold
    OWNS = "OWNS"                  # src is the authority for dst
    IMPLEMENTS = "IMPLEMENTS"      # src realises the contract in dst
    MENTIONS = "MENTIONS"          # src refers to entity dst


#: Relationships that cascade staleness from destination to source.
PROPAGATING_RELS: set[str] = {RelType.DEPENDS_ON.value, RelType.INFORMS.value}


class Entity(BaseModel):
    """Workspace-scoped graph entity that crosses canon-domain boundaries.

    Retained from the August detour's real graph engine — positioning-neutral.
    """
    model_config = ConfigDict(populate_by_name=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str = "default"
    name: str
    normalized_name: str = ""
    entity_type: str = "concept"
    description: str = ""
    aliases: list[str] = Field(default_factory=list)


class Edge(BaseModel):
    """Typed cross-domain edge. Retained from the August detour — positioning-neutral."""
    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str = "default"
    src_type: NodeType
    src_id: str
    dst_type: NodeType
    dst_id: str
    rel_type: RelType
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: str = ""
    created_by: str = ""


class CanonDomain(BaseModel):
    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)

    id: UUID = Field(default_factory=uuid4)
    name: str
    source: str = "manual"
    source_id: str | None = None
    grounding_type: GroundingType = Field(default=GroundingType.MESSAGE_HOUSE, validation_alias=AliasChoices('grounding_type', 'document_type'), serialization_alias='grounding_type')
    summary: str = ""
    audience: str = ""
    brand_personality: str = ""
    positioning: str = ""
    tagline: str = ""
    differentiation: str = ""
    status: DomainStatus = DomainStatus.ACTIVE
    department: str = "General"
    last_synced: datetime | None = None
    last_reviewed: datetime | None = None
    # Phase 2 additions:
    parent_domain_id: UUID | None = None
    inheritance_policy: InheritancePolicy = InheritancePolicy.FULL
    dri: str = ""

    @property
    def document_type(self) -> GroundingType:
        return self.grounding_type

    @document_type.setter
    def document_type(self, value: GroundingType) -> None:
        self.grounding_type = value

    def is_stale(self, days: int = 90) -> bool:
        """Check if framework is stale (>days since last_reviewed or created)."""
        now = datetime.now()
        if self.last_reviewed:
            return (now - self.last_reviewed).days > days
        return True  # No review date means stale by default


MessageHouse = CanonDomain  # Deprecated alias


class CanonEntry(BaseModel):
    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)

    id: UUID = Field(default_factory=uuid4)
    canon_domain_id: UUID = Field(validation_alias=AliasChoices('canon_domain_id', 'message_house_id'), serialization_alias='canon_domain_id')
    pillar_id: int | None = None
    section_type: SectionType
    priority: int = Field(ge=1, le=5)
    content: str
    status: EntryStatus = EntryStatus.DRAFT
    approved_by: str | None = None
    approved_at: datetime | None = None
    content_tier: ContentTier | None = None
    dri: str = ""

    @field_validator('priority', mode='before')
    @classmethod
    def clamp_priority(cls, v):
        try:
            return max(1, min(5, int(v)))
        except (TypeError, ValueError):
            return 3
    variants: dict[str, str] = Field(default_factory=dict)
    personas: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    source_chunk_id: str | None = None

    @property
    def message_house_id(self) -> UUID:
        return self.canon_domain_id

    @message_house_id.setter
    def message_house_id(self, value: UUID) -> None:
        self.canon_domain_id = value


KeyMessage = CanonEntry  # Deprecated alias


class Pillar(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: int
    canon_domain_id: str = Field(validation_alias=AliasChoices('canon_domain_id', 'house_id'), serialization_alias='canon_domain_id')
    name: str
    description: str | None = None
    display_order: int = 0

    @property
    def house_id(self) -> str:
        return self.canon_domain_id

    @house_id.setter
    def house_id(self, value: str) -> None:
        self.canon_domain_id = value


class PillarCreate(BaseModel):
    name: str
    description: str | None = None
    display_order: int = 0


class PillarUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    display_order: int | None = None


class Persona(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: UUID = Field(default_factory=uuid4)
    canon_domain_id: UUID = Field(validation_alias=AliasChoices('canon_domain_id', 'message_house_id'), serialization_alias='canon_domain_id')
    name: str
    description: str = ""
    pain_points: list[str] = Field(default_factory=list)
    buying_triggers: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    status: EntryStatus = EntryStatus.DRAFT
    approved_by: str | None = None
    approved_at: datetime | None = None

    @field_validator("pain_points", "buying_triggers", mode="before")
    @classmethod
    def coerce_str_list(cls, v):
        return [i.get("content", str(i)) if isinstance(i, dict) else str(i) for i in (v or [])]

    @field_validator("objections", mode="before")
    @classmethod
    def coerce_objections(cls, v):
        return [i.get("statement", str(i)) if isinstance(i, dict) else str(i) for i in (v or [])]

    @property
    def message_house_id(self) -> UUID:
        return self.canon_domain_id

    @message_house_id.setter
    def message_house_id(self, value: UUID) -> None:
        self.canon_domain_id = value


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
    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)

    id: str
    canon_domain_id: UUID = Field(validation_alias=AliasChoices('canon_domain_id', 'message_house_id'), serialization_alias='canon_domain_id')
    canon_entry_id: UUID | None = Field(default=None, validation_alias=AliasChoices('canon_entry_id', 'key_message_id'), serialization_alias='canon_entry_id')
    content: str
    section_type: SectionType
    priority: int
    persona: str | None = None
    channel: Channel = Channel.ALL
    canon_domain_name: str = Field(default="", validation_alias=AliasChoices('canon_domain_name', 'house_name'), serialization_alias='canon_domain_name')
    canon_domain_summary: str = Field(default="", validation_alias=AliasChoices('canon_domain_summary', 'house_summary'), serialization_alias='canon_domain_summary')
    last_synced: datetime | None = None
    content_tier: str | None = None

    @property
    def message_house_id(self) -> UUID:
        return self.canon_domain_id

    @message_house_id.setter
    def message_house_id(self, value: UUID) -> None:
        self.canon_domain_id = value

    @property
    def key_message_id(self) -> UUID | None:
        return self.canon_entry_id

    @key_message_id.setter
    def key_message_id(self, value: UUID | None) -> None:
        self.canon_entry_id = value

    @property
    def house_name(self) -> str:
        return self.canon_domain_name

    @house_name.setter
    def house_name(self, value: str) -> None:
        self.canon_domain_name = value

    @property
    def house_summary(self) -> str:
        return self.canon_domain_summary

    @house_summary.setter
    def house_summary(self, value: str) -> None:
        self.canon_domain_summary = value


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
    model_config = ConfigDict(populate_by_name=True)
    active_canon_domain_id: UUID | None = Field(default=None, validation_alias=AliasChoices('active_canon_domain_id', 'active_house_id'), serialization_alias='active_canon_domain_id')
    canon_domain_name: str = Field(default="", validation_alias=AliasChoices('canon_domain_name', 'house_name'), serialization_alias='canon_domain_name')
    canon_domain_summary: str = Field(default="", validation_alias=AliasChoices('canon_domain_summary', 'house_summary'), serialization_alias='canon_domain_summary')
    active_personas: list[str] = Field(default_factory=list)
    used_chunks: int = 0
    confidence: str = "medium"
    coverage: dict[str, str] = Field(default_factory=dict)
    gaps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def active_house_id(self) -> UUID | None:
        return self.active_canon_domain_id

    @active_house_id.setter
    def active_house_id(self, value: UUID | None) -> None:
        self.active_canon_domain_id = value

    @property
    def house_name(self) -> str:
        return self.canon_domain_name

    @house_name.setter
    def house_name(self, value: str) -> None:
        self.canon_domain_name = value

    @property
    def house_summary(self) -> str:
        return self.canon_domain_summary

    @house_summary.setter
    def house_summary(self, value: str) -> None:
        self.canon_domain_summary = value


class GroundingResponse(BaseModel):
    results: list[GroundingResult]
    grounding_context: GroundingContext


COMPLETE_FRAMEWORK_SPEC = {
    "description": "Definition of a complete MsgStack canon framework (canon domain).",
    "domain_fields": {
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
    "canon_entry_fields": {
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
        "All 7 section types have at least 1 canon entry",
        "headline, subhead, benefit, proof_point have 3+ entries each",
        "At least 2 personas defined with all fields",
        "All canon entries have linkedin and email variants",
        "Positioning statement is a full sentence (50+ chars)",
        "Tagline is present and under 60 chars",
        "Differentiation is specific and comparative (not generic)",
    ],
}

COMPLETE_FRAMEWORK_SPEC["house_fields"] = COMPLETE_FRAMEWORK_SPEC["domain_fields"]
COMPLETE_FRAMEWORK_SPEC["key_message_fields"] = COMPLETE_FRAMEWORK_SPEC["canon_entry_fields"]


class ArtifactRating(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    artifact_id: str
    rating: int  # 1-5, or mapped from good/bad
    tag: str = "good"  # "good" or "bad"
    rated_by: str = ""
    timestamp: datetime
    notes: str = ""


class ChunkUsageStat(BaseModel):
    chunk_id: str
    times_used: int = 0
    avg_rating: float = 0.0
    boost_factor: float = 1.0


class BrandSettings(BaseModel):
    # Defaults follow the ATLAS design system (ink on paper, atlas-blue accent)
    workspace_id: str
    primary_color: str = "#3E4E80"
    secondary_color: str = "#EFEADD"
    accent_color: str = "#C05A1E"
    background_color: str = "#F6F3EA"
    text_color: str = "#23201A"
    font_heading: str = "Newsreader"
    font_body: str = "Instrument Sans"
    logo_path: str | None = None


def resolve_brand_tokens(workspace_id: str, design_spec: "DesignSpec") -> "DesignSpec":
    """Apply workspace brand settings to a DesignSpec (modifies in place, returns same object)."""
    from src.design.schema_v2 import ZoneType
    from src.store import get_store

    store = get_store()
    brand = store.get_brand_settings(workspace_id)
    if not brand:
        return design_spec

    design_spec.brand_tokens = {
        "primary_color": brand.primary_color,
        "secondary_color": brand.secondary_color,
        "accent_color": brand.accent_color,
        "background_color": brand.background_color,
        "text_color": brand.text_color,
        "font_heading": brand.font_heading,
        "font_body": brand.font_body,
        "logo_path": brand.logo_path,
    }

    for z in design_spec.zones:
        if "brand" in z.brand_refs or not z.brand_refs:
            if z.type == ZoneType.HEADER or z.type == ZoneType.CTA_FOOTER:
                if not z.background:
                    z.background = brand.primary_color
            if z.type == ZoneType.HERO and not z.background:
                z.background = brand.secondary_color

    return design_spec


class SearchFilters(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    section_types: list[str] | None = None
    personas: list[str] | None = None
    channels: list[str] | None = None
    canon_domains: list[str] | None = Field(default=None, validation_alias=AliasChoices('canon_domains', 'message_houses'), serialization_alias='canon_domains')
    include_variants: bool = True
    min_priority: int | None = None
    min_confidence: float | None = None
    include_drafts: bool = False
    include_unapproved: bool = False

    @property
    def message_houses(self) -> list[str] | None:
        return self.canon_domains

    @message_houses.setter
    def message_houses(self, value: list[str] | None) -> None:
        self.canon_domains = value


class UserProfile(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    email: str
    name: str
    department: str
    is_admin: bool = False


class ElementPermission(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    target_id: UUID  # References CanonDomain or CanonEntry ID
    role: UserRole


class ArtifactEntryBinding(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    artifact_id: UUID
    canon_entry_id: UUID
    element_type: str  # e.g., "tagline", "proof_point"
    bound_text: str


class TemporaryCanonOverlay(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    content: str
    priority: int = 1
    created_by: str
    expires_at: datetime


class QueryAuditLog(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str = "default"
    session_id: str = ""
    user_id: str = ""  # caller identity: API-key name, "mcp-session", or "web"
    query_text: str
    model_used: str = ""
    artifacts_used: list[str] = Field(default_factory=list)
    entries_used: list[str] = Field(default_factory=list)
    domain_ids: list[str] = Field(default_factory=list)
    top_confidence: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)
    latency_ms: float = 0.0
    tokens_used: int = 0
    source: str = ""  # e.g. "mcp:search_canon", "web:chat"
