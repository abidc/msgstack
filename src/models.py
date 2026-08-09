"""Data models for MsgStack MCP."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, AliasChoices


class AssertionType(str, Enum):
    """What kind of fact an assertion states.

    Engineering-shaped: these are the categories a service owner actually
    maintains. The previous set (headline / benefit / proof_point /
    social_proof) described marketing copy and is gone — see STRATEGY_V2.md §6.
    """
    CONSTRAINT = "constraint"                  # a limit: rate, size, quota
    SLA = "sla"                                # a commitment: uptime, latency
    DEPRECATION = "deprecation"                # a sunset with a date
    CONFIG_DEFAULT = "config_default"          # what a setting is unless changed
    DEPENDENCY = "dependency"                  # what this needs to function
    CAPABILITY = "capability"                  # what it can do
    LIMITATION = "limitation"                  # what it deliberately cannot do
    SECURITY_POSTURE = "security_posture"      # authn/authz/compliance statement
    INTERFACE_CONTRACT = "interface_contract"  # request/response shape, schema
    VERSION_POLICY = "version_policy"          # compatibility and support window
    RUNBOOK_STEP = "runbook_step"              # an operational instruction
    DECISION = "decision"                      # an ADR: choice + rationale
    POSITIONING = "positioning"                # one-line summary of the subject
    SOURCE_MARKDOWN = "source_markdown"        # raw ingested document chunk


#: Historical assertion_type values -> AssertionType. Applied once at migration.
#: Anything absent here is mapped to CAPABILITY and flagged for review rather
#: than dropped — losing a fact silently is worse than mis-typing one.
LEGACY_SECTION_TYPE_MAP: dict[str, str] = {
    "positioning":           AssertionType.POSITIONING.value,
    "source_markdown":       AssertionType.SOURCE_MARKDOWN.value,
    "benefit":               AssertionType.CAPABILITY.value,
    "use_case":              AssertionType.CAPABILITY.value,
    "headline":              AssertionType.POSITIONING.value,
    "subhead":               AssertionType.POSITIONING.value,
    "proof_point":           AssertionType.SLA.value,
    "qa_pair":             AssertionType.LIMITATION.value,
    "competitor_weakness":   AssertionType.LIMITATION.value,
    "competitor_strength":   AssertionType.CAPABILITY.value,
    "competitive_response":  AssertionType.POSITIONING.value,
    "social_proof":          AssertionType.CAPABILITY.value,
    "know_your_market":      AssertionType.POSITIONING.value,
    "brand_voice":           AssertionType.POSITIONING.value,
    "style_rule":            AssertionType.CONSTRAINT.value,
    "word_list":             AssertionType.CONSTRAINT.value,
    "narrative_pillar":      AssertionType.POSITIONING.value,
    "company_value":         AssertionType.POSITIONING.value,
    "founding_story":        AssertionType.POSITIONING.value,
    "persona_detail":         AssertionType.CAPABILITY.value,
}


class SchemaType(str, Enum):
    """The shape of a spec — which assertion types and sections it expects."""
    ENGINEERING_SPEC = "engineering_spec"   # default: a service or component
    SERVICE_CATALOG = "service_catalog"     # an inventory of services
    POLICY_SHIELD = "policy_shield"         # legal/compliance assertions
    INCIDENT_RECORD = "incident_record"     # postmortems and their findings


DEPARTMENT_PRIMARY_SCHEMA = {
    "General": SchemaType.ENGINEERING_SPEC,
    "Engineering": SchemaType.ENGINEERING_SPEC,
    "Platform": SchemaType.SERVICE_CATALOG,
    "Security": SchemaType.POLICY_SHIELD,
    "Operations": SchemaType.INCIDENT_RECORD,
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


class SpecStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    NEEDS_REVIEW = "needs_review"



class AssertionStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    OUTDATED = "outdated"
    LOCKED = "locked"



class ContentTier(str, Enum):
    TIER_1_LOCKED = "tier_1_locked"
    TIER_2_STRUCTURED = "tier_2_structured"
    TIER_3_GROUNDED = "tier_3_grounded"


class ArtifactStatus(str, Enum):
    DRAFT = "draft"
    INTERNAL_REVIEW = "internal_review"
    APPROVED = "approved"


class NodeType(str, Enum):
    """Node kinds an edge may connect."""
    ASSERTION = "assertion"
    SPEC = "spec"
    ENTITY = "entity"


class RelType(str, Enum):
    """Typed graph relationships.

    DEPENDS_ON and INFORMS are the propagation-bearing edges: a change to the
    destination marks the source stale. The rest are navigational.
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
    model_config = ConfigDict(populate_by_name=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str = "default"
    name: str
    normalized_name: str = ""
    entity_type: str = "concept"
    description: str = ""
    aliases: list[str] = Field(default_factory=list)


class Edge(BaseModel):
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


class InheritancePolicy(str, Enum):
    FULL = "full"
    SELECTIVE_OVERRIDE = "selective_override"
    VOCAB_CONSTRAINED = "vocab_constrained"
    AUTONOMOUS = "autonomous"


class Spec(BaseModel):
    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)

    id: UUID = Field(default_factory=uuid4)
    name: str
    source: str = "manual"
    source_id: str | None = None
    schema_type: SchemaType = SchemaType.ENGINEERING_SPEC
    summary: str = ""
    audience: str = ""
    # Free-text register/tone. Kept from the PMM schema because it is generic:
    # a runbook and a public changelog want different registers.
    brand_personality: str = ""
    positioning: str = ""
    tagline: str = ""
    differentiation: str = ""
    status: SpecStatus = SpecStatus.ACTIVE
    department: str = "General"
    last_synced: datetime | None = None
    last_reviewed: datetime | None = None
    # Phase 2 additions:
    parent_domain_id: UUID | None = None
    inheritance_policy: InheritancePolicy = InheritancePolicy.FULL
    dri: str = ""

    def is_stale(self, days: int = 90) -> bool:
        """Check if framework is stale (>days since last_reviewed or created)."""
        now = datetime.now()
        if self.last_reviewed:
            return (now - self.last_reviewed).days > days
        return True  # No review date means stale by default



class Assertion(BaseModel):
    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)

    id: UUID = Field(default_factory=uuid4)
    spec_id: UUID = Field(validation_alias=AliasChoices('spec_id', 'spec_id'), serialization_alias='spec_id')
    pillar_id: int | None = None
    assertion_type: AssertionType
    priority: int = Field(ge=1, le=5)
    content: str
    status: AssertionStatus = AssertionStatus.DRAFT
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
    audiences: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    source_chunk_id: str | None = None



class Pillar(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: int
    spec_id: str = Field(validation_alias=AliasChoices('spec_id', 'spec_id'), serialization_alias='spec_id')
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


class Audience(BaseModel):
    """Who an assertion is being rendered for.

    Audience-conditioned retrieval is a general mechanism, not a marketing one:
    the same constraint reads differently for a new hire, an on-call engineer
    and an integrating partner. This is the old Audience model with its
    buyer-journey children (pain_points, buying_triggers) removed.
    """
    model_config = ConfigDict(populate_by_name=True)
    id: UUID = Field(default_factory=uuid4)
    spec_id: UUID = Field(validation_alias=AliasChoices('spec_id', 'canon_domain_id'), serialization_alias='spec_id')
    name: str
    description: str = ""
    qa_pairs: list[str] = Field(default_factory=list)
    status: AssertionStatus = AssertionStatus.DRAFT
    approved_by: str | None = None
    approved_at: datetime | None = None

    @field_validator("qa_pairs", mode="before")
    @classmethod
    def coerce_qa_pairs(cls, v):
        return [i.get("statement", str(i)) if isinstance(i, dict) else str(i) for i in (v or [])]


class QAPair(BaseModel):
    """A statement paired with its response.

    Kept from the old QAPair model because the shape is independently
    useful: FAQ entries, known-issue/workaround pairs, and the rejected
    alternatives in an ADR are all this.
    """
    id: int
    audience_id: str
    statement: str
    response: str | None = None


class GroundingChunk(BaseModel):
    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)

    id: str
    spec_id: UUID = Field(validation_alias=AliasChoices('spec_id', 'spec_id'), serialization_alias='spec_id')
    assertion_id: UUID | None = Field(default=None, validation_alias=AliasChoices('assertion_id', 'assertion_id'), serialization_alias='assertion_id')
    content: str
    assertion_type: AssertionType
    priority: int
    audience: str | None = None
    channel: Channel = Channel.ALL
    spec_name: str = Field(default="", validation_alias=AliasChoices('spec_name', 'spec_name'), serialization_alias='spec_name')
    spec_summary: str = Field(default="", validation_alias=AliasChoices('spec_summary', 'spec_summary'), serialization_alias='spec_summary')
    last_synced: datetime | None = None
    content_tier: str | None = None


class GroundingResult(BaseModel):
    chunk_id: str
    content: str
    assertion_type: str
    priority: int
    audience: str | None
    channel: str
    channel_variants: dict[str, str] = Field(default_factory=dict)
    source: dict
    confidence: float = Field(ge=0.0, le=1.0)
    rerank_reason: str = ""


class GroundingContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    active_spec_id: UUID | None = Field(default=None, validation_alias=AliasChoices('active_spec_id', 'active_spec_id'), serialization_alias='active_spec_id')
    spec_name: str = Field(default="", validation_alias=AliasChoices('spec_name', 'spec_name'), serialization_alias='spec_name')
    spec_summary: str = Field(default="", validation_alias=AliasChoices('spec_summary', 'spec_summary'), serialization_alias='spec_summary')
    active_audiences: list[str] = Field(default_factory=list)
    used_chunks: int = 0
    confidence: str = "medium"
    coverage: dict[str, str] = Field(default_factory=dict)
    gaps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GroundingResponse(BaseModel):
    results: list[GroundingResult]
    grounding_context: GroundingContext


COMPLETE_SCHEMA_SPEC = {
    "description": "Definition of a complete MsgStack spec (spec).",
    "domain_fields": {
        "name": "Brand or product name",
        "summary": "1-2 sentence product overview",
        "positioning": "Full positioning statement — for [audience] who [need], [product] is [category] that [benefit]. Unlike [alt], [product] [key differentiator].",
        "tagline": "7 words or fewer. Memorable and ownable.",
        "differentiation": "2-3 specific ways this is better than alternatives (not just different).",
        "audience": "Firmographic/demographic definition: role, company size, industry.",
        "status": "active | archived | needs_review",
    },
    "required_assertion_types": {
        "headline": "Attention-grabbing primary messages. Min 3. Priority 1 = most important.",
        "subhead": "Supporting messages that expand on headlines. Min 3.",
        "benefit": "Specific value props with evidence or metrics. Min 4.",
        "proof_point": "Quantified stats, customer counts, analyst citations. Min 3.",
        "qa_pair": "Common qa_pairs with concise counter-messaging. Min 3.",
        "social_proof": "Customer quotes, awards, media mentions, G2/analyst recognition. Min 3.",
        "positioning": "Core positioning message in key-message form. Min 1.",
    },
    "assertion_fields": {
        "content": "The core message in plain language.",
        "priority": "1 (highest) to 5. Top 3 should be the sharpest messages.",
        "audiences": "Which audiences this message is most relevant for.",
        "channels": "Channels where this message appears. 'all' = universal.",
        "variants": {
            "linkedin": "LinkedIn-optimized version (conversational, 15-20 words max)",
            "email": "Email subject-line or body hook version (40-60 chars)",
            "paid": "Paid ad version (punchy, benefit-first, 10-15 words)",
            "twitter": "Twitter/X version (under 240 chars with punch)",
        },
    },
    "audience_fields": {
        "name": "Role title (e.g. CISO, VP Sales, HR Manager)",
        "description": "Who they are, what they own, what success looks like for them.",
        "qa_pairs": "2-4 reasons they hesitate to buy or switch.",
    },
    "minimum_audiences": 2,
    "completeness_checklist": [
        "All 7 section types have at least 1 assertion",
        "headline, subhead, benefit, proof_point have 3+ entries each",
        "At least 2 audiences defined with all fields",
        "All assertions have linkedin and email variants",
        "Positioning statement is a full sentence (50+ chars)",
        "Tagline is present and under 60 chars",
        "Differentiation is specific and comparative (not generic)",
    ],
}


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
    assertion_types: list[str] | None = None
    audiences: list[str] | None = None
    channels: list[str] | None = None
    specs: list[str] | None = Field(default=None, validation_alias=AliasChoices('specs', 'canon_domains'), serialization_alias='specs')
    include_variants: bool = True
    min_priority: int | None = None
    min_confidence: float | None = None
    include_drafts: bool = False
    include_unapproved: bool = False


class ArtifactEntryBinding(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    artifact_id: UUID
    assertion_id: UUID
    element_type: str  # e.g., "tagline", "proof_point"
    bound_text: str


