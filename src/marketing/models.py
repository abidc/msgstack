"""Pydantic models for the marketing slice.

Vocabulary (kept deliberately plain — these are the nouns a small-business owner
or an agency account manager already uses):

- **Brand** — the tenant. One per client for an agency, one for a solo operator.
- **VoiceCanon** — the brand's approved voice and claims, versioned. The
  ``locked_claims`` list is the Tier-1 idea from the core product: text that
  must appear verbatim or not at all.
- **ContentItem** — one draft for one channel on one day, with its gate result.
- **Approval** — a human decision on a ContentItem, always with a reason on reject.
- **Schedule** — the "this is going out" record created when an item is approved.
- **ResultRecord** — what actually shipped (and, later, how it did).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import ClassVar, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ContentStatus(str, Enum):
    DRAFT = "draft"              # gate passed (or soft-only); waiting for a decision
    NEEDS_REWORK = "needs_rework"  # gate found a hard violation; cannot be approved as-is
    APPROVED = "approved"        # human said yes; a Schedule row exists
    REJECTED = "rejected"        # human said no, with a reason
    SCHEDULED = "scheduled"      # alias state used on the Schedule row
    PUBLISHED = "published"      # a ResultRecord exists
    FAILED = "failed"


class Autonomy(str, Enum):
    """Borrowed from Syd's stage-for-yes rule: nothing publishes without a human
    decision unless the brand has explicitly earned/enabled a looser tier.
    Only APPROVE_EACH is implemented in this slice; the others are reserved so
    the data model does not need a migration when they land."""
    APPROVE_EACH = "approve_each"
    AUTO_SCHEDULE_CLEAN = "auto_schedule_clean"  # reserved: clean gate → schedule, digest afterwards
    AUTOPILOT = "autopilot"                      # reserved: never default


class Brand(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str = "default"
    name: str
    slug: str = ""
    owner: str = ""                    # who approves (email or handle)
    kind: str = "solo"                 # solo | agency_client | dtc | other
    autonomy: Autonomy = Autonomy.APPROVE_EACH
    weekly_quota: dict[str, int] = Field(default_factory=dict)  # channel -> max open drafts+scheduled per week
    created_at: datetime = Field(default_factory=_utcnow)


class VoiceCanon(BaseModel):
    """The ten-minute intake produces one of these. Every field is optional on
    purpose: `completeness()` tells the caller what is still missing rather than
    refusing to start."""
    id: UUID = Field(default_factory=uuid4)
    brand_id: UUID
    version: int = 1
    one_liner: str = ""                 # what we do, for whom, in one sentence
    audience: str = ""                  # who reads this
    tone: list[str] = Field(default_factory=list)          # 3-5 adjectives
    we_say: list[str] = Field(default_factory=list)        # words/phrases to use
    we_never_say: list[str] = Field(default_factory=list)  # banned words/phrases (hard)
    locked_claims: list[str] = Field(default_factory=list) # Tier-1: verbatim or absent
    topics: list[str] = Field(default_factory=list)        # content pillars to rotate
    off_limits: list[str] = Field(default_factory=list)    # topics never to write about (hard)
    cta: str = ""                                          # the standing call to action
    example_posts: list[str] = Field(default_factory=list) # up to 3 real pieces in the owner's voice
    max_words: dict[str, int] = Field(default_factory=dict)  # per-channel override
    allow_first_person_experience: bool = False  # generated text may not invent "I've seen..."
    notes: str = ""
    created_at: datetime = Field(default_factory=_utcnow)

    # Fields that matter most for a usable canon, in the order the intake asks them.
    REQUIRED_FOR_GENERATION: ClassVar[tuple[str, ...]] = ("one_liner", "audience", "tone", "topics", "cta")

    def missing(self) -> list[str]:
        out = []
        for f in ("one_liner", "audience", "tone", "we_never_say", "locked_claims",
                  "topics", "cta", "example_posts"):
            v = getattr(self, f)
            if not v:
                out.append(f)
        return out

    def completeness(self) -> int:
        fields = ("one_liner", "audience", "tone", "we_say", "we_never_say",
                  "locked_claims", "topics", "off_limits", "cta", "example_posts")
        filled = sum(1 for f in fields if getattr(self, f))
        return int(round(100 * filled / len(fields)))

    def ready_for_generation(self) -> bool:
        return all(getattr(self, f) for f in self.REQUIRED_FOR_GENERATION)


class GateViolation(BaseModel):
    rule: str
    severity: str = "soft"   # hard | soft
    message: str
    span: str = ""


class GateResult(BaseModel):
    ok: bool = True                 # no hard violations
    clean: bool = True              # no violations at all
    violations: list[GateViolation] = Field(default_factory=list)
    words: int = 0
    version: str = ""

    @property
    def hard(self) -> list[GateViolation]:
        return [v for v in self.violations if v.severity == "hard"]

    @property
    def soft(self) -> list[GateViolation]:
        return [v for v in self.violations if v.severity == "soft"]

    @property
    def rules(self) -> list[str]:
        return [v.rule for v in self.violations]


class ContentItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    brand_id: UUID
    canon_version: int = 1
    channel: str                       # linkedin | newsletter | instagram | x | blog
    slot_date: Optional[date] = None   # the day in the week plan this draft fills
    topic: str = ""
    body: str
    status: ContentStatus = ContentStatus.DRAFT
    gate: GateResult = Field(default_factory=GateResult)
    generated_by: str = "manual"       # manual | template | llm:<model>
    rewrite_count: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Approval(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    brand_id: UUID
    content_id: UUID
    decision: str                      # approve | reject
    reason: str = ""
    decided_by: str = ""
    override_hard: bool = False        # approver knowingly accepted a hard violation
    decided_at: datetime = Field(default_factory=_utcnow)


class Schedule(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    brand_id: UUID
    content_id: UUID
    channel: str
    publish_at: datetime
    destination: str = "manual"        # manual | buffer | listmonk | linkedin | ...
    status: str = "scheduled"          # scheduled | published | failed | cancelled
    external_ref: str = ""             # id/url at the destination once known
    created_at: datetime = Field(default_factory=_utcnow)


class ResultRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    brand_id: UUID
    content_id: UUID
    channel: str
    published_at: datetime
    external_ref: str = ""
    metrics: dict = Field(default_factory=dict)  # impressions, clicks, opens... filled later
    captured_at: datetime = Field(default_factory=_utcnow)
