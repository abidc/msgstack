"""Tool functions for the marketing slice.

These are plain functions returning JSON-serialisable dicts. ``src/server.py``
wraps each one as an MCP tool and ``src/marketing/api.py`` as a REST route, so
the behaviour (and the tests) live in one place. Every function that touches
content takes ``brand_id`` first: the brand is the tenant and the store refuses
cross-brand reads.

Autonomy model (borrowed from Syd): drafts are *staged*; a human says yes or no
(``approve_content`` / ``reject_content``, reject requires a reason). Approval
creates the Schedule record. A hard gate violation cannot be approved without
an explicit ``override=True`` plus a reason, and the override is recorded.
Weekly quota per channel (borrowed from Syd's Plan Gate) caps how many drafts
``generate_week`` will leave open, so an agent in a loop cannot flood the queue.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from uuid import UUID

from . import generator as gen
from .models import (Approval, Brand, ContentItem, ContentStatus, ResultRecord, Schedule,
                     VoiceCanon)
from .store import MarketingStore, NotFound, get_marketing_store
from .voice_gate import GATE_VERSION, lint

INTAKE_QUESTIONS = {
    "one_liner": "In one sentence: what do you do, and for whom?",
    "audience": "Who exactly reads this? Describe one person, not a market.",
    "tone": "Give three to five words for how you want to sound (and one for how you never want to sound).",
    "we_never_say": "Words or phrases you never want to see in your copy (jargon, competitor terms, cliches).",
    "locked_claims": "Any claim, number, price or tagline that must appear exactly as written or not at all.",
    "topics": "Three to six topics you want to be known for. We rotate through these.",
    "cta": "What should a reader do next, in your words?",
    "example_posts": "Paste one to three things you wrote yourself that sound like you.",
}

_WEEKLY_QUOTA_DEFAULT = 5


def _store(store: Optional[MarketingStore]) -> MarketingStore:
    return store or get_marketing_store()


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:60] or "brand"


def _uuid(v: str | UUID, what: str) -> UUID:
    try:
        return UUID(str(v))
    except Exception:
        raise ValueError(f"{what} must be a UUID, got {v!r}")


def _canon_view(canon: VoiceCanon) -> dict:
    d = canon.model_dump(mode="json")
    d["completeness"] = canon.completeness()
    d["missing"] = canon.missing()
    d["ready_for_generation"] = canon.ready_for_generation()
    d["next_questions"] = [INTAKE_QUESTIONS[f] for f in canon.missing() if f in INTAKE_QUESTIONS][:3]
    return d


def _item_view(item: ContentItem) -> dict:
    d = item.model_dump(mode="json")
    d["gate"]["hard"] = [v.model_dump() for v in item.gate.hard]
    d["gate"]["soft"] = [v.model_dump() for v in item.gate.soft]
    d["gate"]["rules"] = item.gate.rules
    return d


# ---------------------------------------------------------------------- intake

def brand_intake(
    name: str,
    one_liner: str = "",
    audience: str = "",
    tone: Optional[list[str]] = None,
    we_say: Optional[list[str]] = None,
    we_never_say: Optional[list[str]] = None,
    locked_claims: Optional[list[str]] = None,
    topics: Optional[list[str]] = None,
    off_limits: Optional[list[str]] = None,
    cta: str = "",
    example_posts: Optional[list[str]] = None,
    owner: str = "",
    kind: str = "solo",
    workspace_id: str = "default",
    weekly_quota: Optional[dict] = None,
    store: Optional[MarketingStore] = None,
) -> dict:
    """Create a brand and version 1 of its voice canon from whatever the intake has so far.

    Partial answers are fine: the response lists what is still missing and the
    next three questions to ask, so a client can run the ten-minute intake as a
    conversation and call ``update_voice_canon`` as answers arrive.
    """
    if not name or not name.strip():
        raise ValueError("name is required")
    st = _store(store)
    brand = Brand(name=name.strip(), slug=_slug(name), owner=owner, kind=kind, workspace_id=workspace_id,
                  weekly_quota=weekly_quota or {})
    st.create_brand(brand)
    canon = VoiceCanon(brand_id=brand.id, one_liner=one_liner.strip(), audience=audience.strip(),
                       tone=[t.strip() for t in (tone or []) if t.strip()],
                       we_say=[t.strip() for t in (we_say or []) if t.strip()],
                       we_never_say=[t.strip() for t in (we_never_say or []) if t.strip()],
                       locked_claims=[t.strip() for t in (locked_claims or []) if t.strip()],
                       topics=[t.strip() for t in (topics or []) if t.strip()],
                       off_limits=[t.strip() for t in (off_limits or []) if t.strip()],
                       cta=cta.strip(), example_posts=[p.strip() for p in (example_posts or []) if p.strip()])
    st.save_canon(canon)
    return {"brand": brand.model_dump(mode="json"), "canon": _canon_view(canon)}


def update_voice_canon(brand_id: str, store: Optional[MarketingStore] = None, **fields) -> dict:
    """Append a new canon version with the given fields changed. Lists replace, not merge."""
    st = _store(store)
    bid = _uuid(brand_id, "brand_id")
    st.get_brand(bid)
    current = st.get_canon(bid) or VoiceCanon(brand_id=bid)
    allowed = {"one_liner", "audience", "tone", "we_say", "we_never_say", "locked_claims", "topics",
               "off_limits", "cta", "example_posts", "max_words", "allow_first_person_experience", "notes"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"unknown canon fields: {sorted(unknown)}")
    data = current.model_dump(exclude={"id", "version", "created_at"})
    data.update({k: v for k, v in fields.items() if v is not None})
    canon = VoiceCanon(**data)
    st.save_canon(canon)
    return {"brand_id": str(bid), "canon": _canon_view(canon)}


def get_brand(brand_id: str, store: Optional[MarketingStore] = None) -> dict:
    st = _store(store)
    bid = _uuid(brand_id, "brand_id")
    brand = st.get_brand(bid)
    canon = st.get_canon(bid)
    return {"brand": brand.model_dump(mode="json"), "canon": _canon_view(canon) if canon else None}


def list_brands(workspace_id: Optional[str] = None, store: Optional[MarketingStore] = None) -> dict:
    st = _store(store)
    out = []
    for b in st.list_brands(workspace_id):
        c = st.get_canon(b.id)
        out.append({**b.model_dump(mode="json"), "canon_version": c.version if c else 0,
                    "completeness": c.completeness() if c else 0})
    return {"brands": out, "count": len(out)}


# ---------------------------------------------------------------------- gate

def check_voice(brand_id: str, text: str, channel: str = "linkedin", kind: str = "post",
                source_text: str = "", store: Optional[MarketingStore] = None) -> dict:
    """Run the voice gate on any text against the brand's current canon. Useful on its own:
    an agent drafting in Claude/ChatGPT can check before it hands copy to Buffer or Mailchimp."""
    st = _store(store)
    bid = _uuid(brand_id, "brand_id")
    st.get_brand(bid)
    canon = st.get_canon(bid)
    res = lint(text, canon, channel=channel, kind=kind, source_text=source_text)
    d = res.model_dump(mode="json")
    d["hard"] = [v.model_dump() for v in res.hard]
    d["soft"] = [v.model_dump() for v in res.soft]
    d["rules"] = res.rules
    d["canon_version"] = canon.version if canon else 0
    return d


# ---------------------------------------------------------------------- generation

def _week_bounds(start: date) -> tuple[date, date]:
    monday = start - timedelta(days=start.weekday())
    return monday, monday + timedelta(days=6)


def generate_week(brand_id: str, channel: str = "linkedin", start_date: Optional[str] = None, count: int = 3,
                  brief: str = "", topics: Optional[list[str]] = None, use_llm: Optional[bool] = None,
                  store: Optional[MarketingStore] = None, llm=None) -> dict:
    """Generate up to ``count`` gated drafts for one channel for the week containing ``start_date``.

    Refuses when the canon is not ready (no one-liner/audience/tone/topics/cta) and
    caps open drafts per channel per week at the brand's ``weekly_quota`` (default 5).
    """
    st = _store(store)
    bid = _uuid(brand_id, "brand_id")
    brand = st.get_brand(bid)
    canon = st.get_canon(bid)
    if canon is None or not canon.ready_for_generation():
        missing = canon.missing() if canon else list(INTAKE_QUESTIONS)
        return {"generated": 0, "items": [], "blocked": "canon_not_ready",
                "missing": missing, "next_questions": [INTAKE_QUESTIONS[f] for f in missing if f in INTAKE_QUESTIONS][:3]}
    if count < 1 or count > 14:
        raise ValueError("count must be between 1 and 14")
    start = date.fromisoformat(start_date) if start_date else date.today()
    wk_start, wk_end = _week_bounds(start)

    quota = int(brand.weekly_quota.get(channel, _WEEKLY_QUOTA_DEFAULT))
    open_now = [i for i in st.list_items(bid, channel=channel, since=wk_start, until=wk_end)
                if i.status in (ContentStatus.DRAFT, ContentStatus.NEEDS_REWORK, ContentStatus.APPROVED)]
    room = quota - len(open_now)
    if room <= 0:
        return {"generated": 0, "items": [], "blocked": "weekly_quota_reached", "quota": quota,
                "open": len(open_now), "week": [wk_start.isoformat(), wk_end.isoformat()]}
    n = min(count, room)

    if llm is None and use_llm is not False:
        llm = gen.default_llm()
    if use_llm is False:
        llm = None
    # rotate topics past what this brand has already covered on this channel
    offset = len(st.list_items(bid, channel=channel))
    items = gen.generate_week(canon, channel, start, n, brief=brief, llm=llm, topics=topics, topic_offset=offset)
    for it in items:
        st.save_item(it)
    return {
        "generated": len(items), "requested": count, "quota": quota, "week": [wk_start.isoformat(), wk_end.isoformat()],
        "mode": "llm" if llm else "template", "gate_version": GATE_VERSION,
        "items": [_item_view(i) for i in items],
        "needs_rework": sum(1 for i in items if i.status == ContentStatus.NEEDS_REWORK),
    }


# ---------------------------------------------------------------------- queue + decisions

def review_queue(brand_id: str, status: Optional[str] = "open", channel: Optional[str] = None,
                 store: Optional[MarketingStore] = None) -> dict:
    """List items awaiting a decision. ``status`` = open (draft + needs_rework), or any ContentStatus."""
    st = _store(store)
    bid = _uuid(brand_id, "brand_id")
    st.get_brand(bid)
    if status == "open" or status is None:
        items = [i for i in st.list_items(bid, channel=channel)
                 if i.status in (ContentStatus.DRAFT, ContentStatus.NEEDS_REWORK)]
    else:
        items = st.list_items(bid, status=ContentStatus(status).value, channel=channel)
    return {"brand_id": str(bid), "count": len(items), "items": [_item_view(i) for i in items]}


def approve_content(brand_id: str, content_id: str, decided_by: str = "", publish_at: Optional[str] = None,
                    destination: str = "manual", reason: str = "", override: bool = False,
                    edited_body: Optional[str] = None, store: Optional[MarketingStore] = None) -> dict:
    """Approve a draft. Creates the Schedule record. Refuses hard gate violations unless
    ``override=True`` with a reason; an edited body is re-gated before approval."""
    st = _store(store)
    bid = _uuid(brand_id, "brand_id")
    item = st.get_item(bid, _uuid(content_id, "content_id"))
    if item.status not in (ContentStatus.DRAFT, ContentStatus.NEEDS_REWORK):
        raise ValueError(f"content is {item.status.value}; only draft or needs_rework items can be approved")
    canon = st.get_canon(bid, item.canon_version) or st.get_canon(bid)
    if edited_body is not None and edited_body.strip() and edited_body != item.body:
        item.body = edited_body.strip()
        item.gate = lint(item.body, canon, channel=item.channel)
        item.generated_by = item.generated_by + "+edited"
    if not item.gate.ok:
        if not override:
            return {"approved": False, "blocked": "hard_violations", "content_id": str(item.id),
                    "hard": [v.model_dump() for v in item.gate.hard],
                    "hint": "fix the text (pass edited_body) or pass override=True with a reason"}
        if not reason.strip():
            raise ValueError("override=True requires a reason")
    when = datetime.fromisoformat(publish_at) if publish_at else datetime.combine(
        item.slot_date or date.today(), time(9, 0))
    if when.tzinfo is not None:
        when = when.astimezone(timezone.utc).replace(tzinfo=None)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    approval = Approval(brand_id=bid, content_id=item.id, decision="approve", reason=reason,
                        decided_by=decided_by, override_hard=(override and not item.gate.ok))
    st.save_approval(approval)
    sched = Schedule(brand_id=bid, content_id=item.id, channel=item.channel, publish_at=when, destination=destination)
    st.save_schedule(sched)
    item.status = ContentStatus.APPROVED
    item.updated_at = now
    st.save_item(item)
    return {"approved": True, "content_id": str(item.id), "approval": approval.model_dump(mode="json"),
            "schedule": sched.model_dump(mode="json")}


def reject_content(brand_id: str, content_id: str, reason: str, decided_by: str = "",
                   store: Optional[MarketingStore] = None) -> dict:
    """Reject a draft. A reason is required: rejections are the training signal."""
    if not reason or not reason.strip():
        raise ValueError("reason is required to reject")
    st = _store(store)
    bid = _uuid(brand_id, "brand_id")
    item = st.get_item(bid, _uuid(content_id, "content_id"))
    if item.status not in (ContentStatus.DRAFT, ContentStatus.NEEDS_REWORK):
        raise ValueError(f"content is {item.status.value}; only draft or needs_rework items can be rejected")
    approval = Approval(brand_id=bid, content_id=item.id, decision="reject", reason=reason.strip(), decided_by=decided_by)
    st.save_approval(approval)
    item.status = ContentStatus.REJECTED
    item.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    st.save_item(item)
    return {"rejected": True, "content_id": str(item.id), "approval": approval.model_dump(mode="json")}


# ---------------------------------------------------------------------- shipped + results

def mark_published(brand_id: str, content_id: str, external_ref: str = "", published_at: Optional[str] = None,
                   metrics: Optional[dict] = None, store: Optional[MarketingStore] = None) -> dict:
    """Record that an approved item actually went out (manually, or via Buffer/listmonk/...).
    This is the results stub: it closes the loop from draft to shipped."""
    st = _store(store)
    bid = _uuid(brand_id, "brand_id")
    item = st.get_item(bid, _uuid(content_id, "content_id"))
    if item.status != ContentStatus.APPROVED:
        raise ValueError(f"content is {item.status.value}; only approved items can be marked published")
    when = datetime.fromisoformat(published_at) if published_at else datetime.now(timezone.utc)
    if when.tzinfo is not None:
        when = when.astimezone(timezone.utc).replace(tzinfo=None)
    sched = st.get_schedule_for(bid, item.id)
    if sched:
        sched.status, sched.external_ref = "published", external_ref or sched.external_ref
        st.save_schedule(sched)
    rec = ResultRecord(brand_id=bid, content_id=item.id, channel=item.channel, published_at=when,
                       external_ref=external_ref, metrics=metrics or {})
    st.save_result(rec)
    item.status = ContentStatus.PUBLISHED
    item.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    st.save_item(item)
    return {"published": True, "content_id": str(item.id), "result": rec.model_dump(mode="json")}


def get_results(brand_id: str, since: Optional[str] = None, store: Optional[MarketingStore] = None) -> dict:
    """Read back what shipped: each published item with its gate result, approval and schedule."""
    st = _store(store)
    bid = _uuid(brand_id, "brand_id")
    st.get_brand(bid)
    since_dt = datetime.fromisoformat(since) if since else None
    if since_dt and since_dt.tzinfo is not None:
        since_dt = since_dt.astimezone(timezone.utc).replace(tzinfo=None)
    results = st.list_results(bid, since=since_dt)
    out = []
    for r in results:
        item = st.get_item(bid, r.content_id)
        approvals = st.list_approvals(bid, r.content_id)
        sched = st.get_schedule_for(bid, r.content_id)
        out.append({
            "content_id": str(r.content_id), "channel": r.channel, "topic": item.topic,
            "published_at": r.published_at.isoformat(), "external_ref": r.external_ref, "metrics": r.metrics,
            "gate_clean": item.gate.clean, "gate_rules": item.gate.rules,
            "approved_by": next((a.decided_by for a in approvals if a.decision == "approve"), ""),
            "override_hard": any(a.override_hard for a in approvals),
            "scheduled_for": sched.publish_at.isoformat() if sched else None,
            "destination": sched.destination if sched else None,
            "body": item.body,
        })
    scheduled = st.list_schedules(bid, status="scheduled")
    return {"brand_id": str(bid), "published": out, "published_count": len(out),
            "scheduled_count": len(scheduled),
            "scheduled": [s.model_dump(mode="json") for s in scheduled]}


__all__ = [
    "NotFound", "brand_intake", "update_voice_canon", "get_brand", "list_brands", "check_voice",
    "generate_week", "review_queue", "approve_content", "reject_content", "mark_published", "get_results",
    "INTAKE_QUESTIONS",
]
