"""Generate a week of drafts for one channel against a brand's voice canon.

Two paths, chosen by whether an LLM is available:

- **LLM path** — one call per draft through the repo's ``llm_client()`` factory
  (OpenRouter), then the voice gate; a draft with violations gets ONE rewrite
  with :func:`voice_gate.rewrite_prompt` and the better version is kept. This
  mirrors the autopilot rule in Syd's content desk (one rewrite, keep the
  better), without its "publish anyway" ending: here the item just lands in
  the queue with its gate result attached.
- **Template path** — no key configured (or ``llm=None`` forced): a plain,
  honest skeleton built only from canon text. It exists so the slice runs
  end-to-end locally and in CI without secrets, and so a user sees the shape
  of the week before paying for a model call. Template drafts are marked
  ``generated_by="template"`` and should read as scaffolding, not copy.

Prompt-writing rule inherited from the voice system: describe requirements,
never demonstrate them with a phrase the model could paste. Examples from the
canon are given as register references and explicitly not as templates.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Callable, Optional

from .models import ContentItem, ContentStatus, VoiceCanon
from .voice_gate import DEFAULT_MAX_WORDS, lint, rewrite_prompt

log = logging.getLogger(__name__)

LLMFn = Callable[[str, str], str]  # (system, user) -> text

CHANNEL_SHAPE = {
    "linkedin": "a LinkedIn post: 80 to 220 words, plain text, no hashtags in the body, no emoji, one idea",
    "newsletter": "a newsletter section: 250 to 700 words, a plain-text heading on the first line, written to one reader",
    "instagram": "an Instagram caption: under 150 words, first line must stand alone as a hook, end with the call to action",
    "x": "a single post for X: under 60 words, no hashtags",
    "blog": "a short blog post: 600 to 1200 words, headed sections, no bullet-point padding",
    "email": "a one-to-one style email: under 300 words, one ask",
}

DEFAULT_WEEKDAYS = {  # which weekdays a channel posts on by default (0 = Monday)
    "linkedin": [0, 2, 4],
    "newsletter": [3],
    "instagram": [0, 2, 4],
    "x": [0, 1, 2, 3, 4],
    "blog": [1],
    "email": [1],
}


def default_llm() -> Optional[LLMFn]:
    """Return an LLM callable if a key is configured, else None (template path)."""
    try:
        from src.config import llm_client, llm_model, settings
    except Exception:  # pragma: no cover - config import failure means no LLM
        return None
    if not (settings.openrouter_api_key or settings.openai_api_key):
        return None
    client = llm_client()
    model = llm_model("gpt-4o-mini")

    def _call(system: str, user: str) -> str:
        resp = client.chat.completions.create(
            model=model, temperature=0.7, max_tokens=1200,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return (resp.choices[0].message.content or "").strip()

    _call.model_name = model  # type: ignore[attr-defined]
    return _call


def week_slots(start: date, channel: str, count: int, weekdays: Optional[list[int]] = None) -> list[date]:
    """Dates for the drafts, walking forward from ``start`` on the channel's posting days."""
    days = weekdays or DEFAULT_WEEKDAYS.get(channel, [0, 2, 4])
    out: list[date] = []
    d = start
    while len(out) < count and (d - start).days < 28:
        if d.weekday() in days:
            out.append(d)
        d += timedelta(days=1)
    while len(out) < count:  # degenerate weekday list; still return the asked count
        out.append(out[-1] + timedelta(days=1) if out else start)
    return out


def pick_topics(canon: VoiceCanon, count: int, offset: int = 0) -> list[str]:
    """Rotate the canon's content pillars so a week never repeats one unless it must."""
    topics = canon.topics or ["what we do and who it is for"]
    return [topics[(offset + i) % len(topics)] for i in range(count)]


def build_system_prompt(canon: VoiceCanon, channel: str) -> str:
    lines = [
        "You write public marketing copy for one brand, in that brand's voice, from a brief.",
        f"Brand, in one line: {canon.one_liner}" if canon.one_liner else "",
        f"Who reads it: {canon.audience}" if canon.audience else "",
        ("Tone words: " + ", ".join(canon.tone)) if canon.tone else "",
        ("Words and phrases this brand uses: " + "; ".join(canon.we_say)) if canon.we_say else "",
        ("Words and phrases this brand never uses: " + "; ".join(canon.we_never_say)) if canon.we_never_say else "",
        ("Topics this brand does not write about at all: " + "; ".join(canon.off_limits)) if canon.off_limits else "",
        "",
        "Claims you may use. If you use one, reproduce it exactly as written, character for character. "
        "If it does not fit, leave it out. Do not paraphrase it, shorten it or round its numbers:",
        *[f"- {c}" for c in canon.locked_claims],
        "",
        "Rules:",
        "- Use no number, statistic, price or date that is not in the brief or the claims above. If you want a figure and do not have one, say it in words or leave it out.",
        "- Do not invent anecdotes, customers, quotes or first-hand experiences. First person is for opinion only.",
        "- Make one point. No balanced essay, no tidy closing lesson, no rhetorical question as a hook.",
        "- No em dashes or en dashes. No stock openers that agree with or label the piece. No hedges that soften the claim to nothing.",
        "- Plain words, contractions are fine, write to one reader.",
        f"- Format: {CHANNEL_SHAPE.get(channel, 'a short piece of public copy')}.",
    ]
    if canon.cta:
        lines.append(f"- End with this call to action, in these words or a close natural variant: {canon.cta}")
    if canon.example_posts:
        lines += ["", "Register references, written by the brand owner. They show the register and sentence length. "
                  "They are not templates: do not reuse their openers, structure or phrases.",
                  *[f"<<<\n{p}\n>>>" for p in canon.example_posts[:3]]]
    lines.append("\nReturn only the copy. No title, no preamble, no quotes around it.")
    return "\n".join(line for line in lines if line is not None)


def build_user_prompt(topic: str, slot: date, brief: str) -> str:
    parts = [f"Topic for this piece: {topic}", f"Publish date: {slot.isoformat()} ({slot.strftime('%A')})"]
    if brief:
        parts.append("Brief / real material to draw from (the only source of facts and figures):\n" + brief)
    else:
        parts.append("No extra material was supplied. Work only from the brand description and the claims. Do not invent specifics.")
    return "\n\n".join(parts)


def template_draft(canon: VoiceCanon, channel: str, topic: str) -> str:
    """Scaffold built only from canon text. Deliberately plain; never pretends to be finished copy."""
    name = canon.one_liner or "This brand"
    who = canon.audience or "the people this is for"
    first = f"On {topic}."
    body = [first, f"{name}", f"Written for {who}."]
    if canon.locked_claims:
        body.append(canon.locked_claims[0])
    if canon.cta:
        body.append(canon.cta)
    text = "\n\n".join(body)
    budget = canon.max_words.get(channel) or DEFAULT_MAX_WORDS.get(channel, 200)
    words = text.split()
    if len(words) > budget:
        text = " ".join(words[:budget])
    return text


def generate_week(
    canon: VoiceCanon,
    channel: str,
    start: date,
    count: int = 3,
    brief: str = "",
    llm: Optional[LLMFn] = None,
    topics: Optional[list[str]] = None,
    topic_offset: int = 0,
    weekdays: Optional[list[int]] = None,
) -> list[ContentItem]:
    """Produce ``count`` gated drafts for ``channel`` starting at ``start``.

    The caller (tools.generate_week) persists the items and enforces quota;
    this function is pure apart from the LLM call so it is easy to test.
    """
    slots = week_slots(start, channel, count, weekdays)
    chosen = topics or pick_topics(canon, count, topic_offset)
    system = build_system_prompt(canon, channel)
    model_name = getattr(llm, "model_name", "llm") if llm else None
    items: list[ContentItem] = []

    for slot, topic in zip(slots, chosen):
        rewrites = 0
        if llm is None:
            body = template_draft(canon, channel, topic)
            generated_by = "template"
        else:
            body = llm(system, build_user_prompt(topic, slot, brief))
            generated_by = f"llm:{model_name}"
        gate = lint(body, canon, channel=channel, source_text=brief)
        if llm is not None and not gate.clean:
            try:
                candidate = llm("You repair short pieces of marketing copy exactly as instructed.",
                                rewrite_prompt(body, gate, canon))
                cgate = lint(candidate, canon, channel=channel, source_text=brief)
                rewrites = 1
                # keep the better version: fewer hard first, then fewer total
                if (len(cgate.hard), len(cgate.violations)) < (len(gate.hard), len(gate.violations)):
                    body, gate = candidate, cgate
            except Exception as e:  # a failed rewrite must never lose the original draft
                log.warning("rewrite failed, keeping original draft: %s", e)
        status = ContentStatus.DRAFT if gate.ok else ContentStatus.NEEDS_REWORK
        items.append(ContentItem(brand_id=canon.brand_id, canon_version=canon.version, channel=channel,
                                 slot_date=slot, topic=topic, body=body, status=status, gate=gate,
                                 generated_by=generated_by, rewrite_count=rewrites))
    return items
