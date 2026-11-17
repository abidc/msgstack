"""Deterministic voice gate.

A port of the rule set in Abid's ``voice-lint/lint_template.js`` (his own code,
written for his LinkedIn automation, 2026-08), generalised so the brand-specific
parts come from a :class:`VoiceCanon` instead of being hard-coded:

- **Universal shape rules** (soft): the tics that make generated copy read as
  generated. Em/en dashes, "X is not A, it is B" antithesis, "Not X. Y."
  staccato, hook-colon openers, rule-of-three lists, stock agreement openers,
  filler phrases, diagnostic hedges, "The real/biggest X" and "Most <group>"
  openers, "X is just Y", "what actually matters", authorless maxims, and
  instruction leakage (announcing the move instead of making it).
- **Truth rules** (hard): a number that does not appear in the canon or the
  brief is a fabricated figure; a first-hand experience claim the brand owner
  did not supply is a fabricated anecdote; a Tier-1 locked claim that is
  referenced but not reproduced verbatim is a paraphrase.
- **Brand rules** (hard): ``we_never_say`` phrases, ``off_limits`` topics.
- **Length** (soft): per-channel word budget, overridable per canon.
- **Comment-only rules** (soft, ``kind="comment"``): implied familiarity,
  unearned verdicts, third-party congratulations, inflation, borrowed exemplar
  phrases. These only make sense when replying to someone else's post.

Two of the original rules were deliberately *not* ported as universals because
they encode one person's stance rather than a general quality signal: the
layoff/workforce scope block and "prescribing to leaders". A brand that wants
them puts the words in ``off_limits``.

Design rule carried over from the JS: every violation quotes the span at fault,
because the rewrite prompt downstream fixes exactly what is quoted and nothing
else. Severity is new: the JS had one list; here hard violations block approval
and soft ones are shown to the approver.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

from .models import GateResult, GateViolation, VoiceCanon

GATE_VERSION = "2026-11-16.1"

# Default word budgets per channel. The JS value (90) was for LinkedIn comments.
DEFAULT_MAX_WORDS = {
    "comment": 90,
    "x": 60,
    "instagram": 150,
    "linkedin": 260,
    "newsletter": 900,
    "blog": 1400,
    "email": 350,
}

_FILLER = [
    "what tends to happen", "the harder truth is", "the whole game", "the real win is",
    "sounds obvious in hindsight", "the part this misses", "what nobody's saying",
    "the gap here is", "directionally right", "what gets lost in", "here's the thing",
    "the truth is", "at the end of the day", "let that sink in", "double-edged sword",
    "unpack", "deep dive", "game changer", "game-changer", "unpopular opinion",
]

_AGREE_OPENERS = [
    "Totally agree", "Completely agree", "I agree", "This resonates", "So true", "Love this",
    "Great point", "Spot on", "Couldn't agree more", "100%", "Well said", "Absolutely",
    "Yes to all of this", "This.",
]

_ANTITHESIS = [
    re.compile(r"\bit'?s not\b[^.?!]{2,80},?\s*it'?s\b", re.I),
    re.compile(r"\bisn'?t\s+(?:just\s+)?(?:about\s+)?[^.?!]{2,80},?\s*it'?s\b", re.I),
    re.compile(r"\bthe real\s+\w+\s+(?:isn'?t|is not)\b", re.I),
    re.compile(r"\b(?:it'?s|that'?s|this is|they'?re)\s+[^,.?!]{2,60},\s*not\s+[^.?!]{2,50}", re.I),
]
_STACCATO = re.compile(r"(?:^|\.\s)Not\s+[^.?!]{2,40}\.\s+[A-Z][^.?!]{2,40}\.")
_HOOK_COLON = re.compile(r"^[^.?!:\n]{3,40}:\s")
_RULE_OF_THREE = re.compile(r"([^,.;:!?\n]{3,60}),\s*([^,.;:!?\n]{3,60}),\s*(?:and|or)\s+([^,.;:!?\n]{3,60})", re.I)
_LOOSE_HEDGE = re.compile(r"\b(?:we\s+often|often\s+mistake|tends?\s+to\s+be|more\s+often\s+than\s+not)\b", re.I)
_MAXIM_UNTIL = re.compile(r"\bworks?\s+until\s+you\b|\b\w+\s+works?\s+until\b", re.I)
_MAXIM_PARALLEL = re.compile(r"\b(\w+)\s+handles?\s+the\s+[\"'“]?\w+[\"'”]?\s+while\s+\w+\s+handles?\b", re.I)

_LEAK = [
    (re.compile(r"\b(?:the|a)\s+(?:less\s+comfortable|blunter|harder|uncomfortable|tougher)\s+(?:version|truth|read|take)\b", re.I),
     "announces the move instead of making it"),
    (re.compile(r"^\s*(?:worth\s+saying|to\s+push\s+back|here'?s\s+another\s+way|playing\s+devil'?s\s+advocate|hot\s+take)\b", re.I),
     "opens by labelling what kind of piece this is"),
    (re.compile(r"\bthe\s+(?:quiet|unspoken)\s+part\b", re.I), "the \"quiet part\" frame"),
]

_FORMULA = [
    (re.compile(r"\b(?:usually|typically)\b", re.I), "formula-hedge",
     "the \"usually/typically\" diagnostic hedge. Either it is true and you can say it plainly, or it is a guess and you can own it"),
    (re.compile(r"\boften\s+(?:just|only|means|ends?\s+up|comes?\s+down\s+to|because)\b", re.I), "formula-hedge",
     "the \"often just ...\" diagnostic hedge. Say it plainly"),
    (re.compile(r"^\s*(?:The|A|An)\s+(?:real|biggest|hardest|only|actual|whole|entire|core|first|last|bigger|harder)\s+\w+", re.I),
     "formula-superlative", "the \"The real/biggest/hardest X ...\" opener, a stock diagnosis frame"),
    (re.compile(r"^\s*Most\s+(?:managers|leaders|companies|people|teams|orgs|organizations|organisations|founders|marketers|devs|developers|engineers|brands|coaches|business\s+owners|of\s+what)\b", re.I),
     "formula-most", "the \"Most <group> ...\" generalisation opener. Talk about the specific thing, not about everybody"),
    (re.compile(r"\b(?:is|are|was|were|becomes?)\s+(?:just|only)\s+(?:a|an|another|the|being)\b", re.I),
     "formula-isjust", "the \"X is just Y\" reduction frame"),
    (re.compile(r"\bwithout\s+[^,.?!]{3,45}\s+(?:is|are|becomes?|turns?\s+into|ends?\s+up)\s+(?:just|often|usually|only|mostly|a\s+way\s+to)\b", re.I),
     "formula-without", "the \"X without Y is just Z\" frame"),
    (re.compile(r"\bwhat\s+(?:actually|really)\s+(?:happens|matters|drives|changes)\b", re.I),
     "formula-whatreally", "the \"what actually happens/matters\" frame"),
]

_FABRICATED_EXPERIENCE = [
    re.compile(r"\b(?:i'?ve|i have)\s+(?:seen|watched|witnessed|worked\s+with|run\s+into|dealt\s+with|noticed|found)\b", re.I),
    re.compile(r"\bin\s+my\s+experience\b", re.I),
    re.compile(r"\bevery\s+[^.?!]{2,40}\s+i'?(?:ve|\s+have)\s+(?:touched|worked|seen|used|tried)\b", re.I),
    re.compile(r"\b(?:when|whenever)\s+i\s+(?:ran|built|shipped|led|coached|managed)\b", re.I),
    re.compile(r"\bi\s+(?:coached|advised|consulted|worked\s+with)\s+(?:a|an|one|some|several)\b", re.I),
]

# Comment-only (replying to a stranger's post).
_FAMILIARITY = [
    re.compile(r"\b(?:been|i'?ve been|have been)\s+(?:watching|following|tracking|rooting for|cheering)\b", re.I),
    re.compile(r"\bkeep(?:ing)?\s+an\s+eye\s+on\b", re.I),
    re.compile(r"\bbig\s+fan\s+of\b", re.I),
    re.compile(r"\balways\s+(?:love|enjoy|read|appreciate)\s+your\b", re.I),
    re.compile(r"\bas\s+(?:we|you\s+and\s+i)\s+(?:discussed|talked\s+about|said)\b", re.I),
    re.compile(r"\bwe'?ve\s+(?:talked|spoken|discussed)\b", re.I),
]
_UNEARNED_VERDICT = [
    re.compile(r"\bwell[\s-]?(?:earned|deserved)\b", re.I),
    re.compile(r"\b(?:so|richly|very|much)\s+deserved\b", re.I),
    re.compile(r"\bno\s+one\s+deserves\s+this\s+more\b", re.I),
]
_THIRD_PARTY = [
    re.compile(r"\b(?:congrats|congratulations|kudos)\b[^.?!]{0,30}\bto\s+your\s+(?:wife|husband|spouse|partner|son|daughter|kid|kids|child|children|mom|mum|mother|dad|father|brother|sister|team|colleague|friend|co-?founder)\b", re.I),
    re.compile(r"\b(?:so|very)\s+proud\s+of\s+(?:your|him|her|them)\b", re.I),
]
_INFLATION = [
    re.compile(r"\b(?:a\s+)?(?:massive|huge|incredible|amazing|enormous|monumental|major)\s+(?:achievement|accomplishment|milestone|deal|win)\b", re.I),
    re.compile(r"\bwhat\s+an\s+(?:achievement|accomplishment|honou?r)\b", re.I),
    re.compile(r"\b(?:this|that)\s+is\s+(?:huge|massive|enormous)\b", re.I),
]
_BORROWED = [
    re.compile(r"\b(?:out|in)\s+(?:in|into)\s+the\s+world\b", re.I),
    re.compile(r"\bgreat\s+to\s+see\s+this\s+one\b", re.I),
]

_NUMBER = re.compile(r"\b\d[\d,.]*%?\b")
_WORD = re.compile(r"\S+")


def _quote(s: str) -> str:
    return '"' + re.sub(r"\s+", " ", str(s).strip()) + '"'


def normalise(text: str) -> str:
    """Mirror the downstream parser's normalisation so the gate sees what will post."""
    t = str(text or "").strip()
    m = re.match(r"^([\"'])([\s\S]*)\1$", t)
    if m:
        t = m.group(2).strip()
    t = t.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def _first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return parts[0] if parts else text


def _numbers(text: str) -> list[str]:
    out = []
    for n in _NUMBER.findall(text):
        # Single digits ("3 things", "a 1:1") are exempt: this is a HARD rule that blocks
        # approval, and a false positive on a list count costs more than a missed "3 classes".
        if re.fullmatch(r"\d", n):
            continue
        out.append(n)
    return out


def _contains_phrase(text_low: str, phrase: str) -> bool:
    p = phrase.strip().lower()
    if not p:
        return False
    # word-boundary match where the phrase starts/ends with a word char
    pat = (r"\b" if p[0].isalnum() else "") + re.escape(p) + (r"\b" if p[-1].isalnum() else "")
    return re.search(pat, text_low) is not None


def lint(
    text: str,
    canon: Optional[VoiceCanon] = None,
    channel: str = "linkedin",
    kind: str = "post",
    source_text: str = "",
    extra_allowed_numbers: Iterable[str] = (),
) -> GateResult:
    """Run every applicable rule and return a :class:`GateResult`.

    ``source_text`` is the brief / material the draft was written from; any
    figure in the draft must appear there or in the canon's locked claims.
    """
    body = normalise(text)
    words = len(_WORD.findall(body))
    res = GateResult(words=words, version=GATE_VERSION)
    V: list[GateViolation] = []

    def add(rule: str, msg: str, span: str = "", severity: str = "soft") -> None:
        V.append(GateViolation(rule=rule, severity=severity, message=msg, span=span))

    if not body or len(body) < 10:
        add("empty", "nothing to lint: text is empty or under 10 characters", body, "hard")
        res.violations = V
        res.ok, res.clean = False, False
        return res

    low = body.lower()
    first = _first_sentence(body)

    # ---------------------------------------------------------------- brand (hard)
    if canon is not None:
        for phrase in canon.we_never_say:
            if _contains_phrase(low, phrase):
                add("banned-phrase", f"uses a phrase this brand never says: {_quote(phrase)}", phrase, "hard")
        for topic in canon.off_limits:
            if _contains_phrase(low, topic):
                add("off-limits-topic", f"touches a topic this brand does not write about: {_quote(topic)}", topic, "hard")
        for claim in canon.locked_claims:
            claim_norm = normalise(claim).lower()
            if not claim_norm:
                continue
            if claim_norm in low:
                continue  # reproduced verbatim: fine
            # Referenced but paraphrased? Any distinctive number from the claim appearing in the draft
            # without the full claim is treated as a paraphrase of a Tier-1 claim.
            for n in _numbers(claim):
                if n in body:
                    add("locked-claim-paraphrase",
                        "references a locked claim without reproducing it verbatim. Tier-1 claims are "
                        f"used exactly as written or not at all. Claim: {_quote(claim)}", n, "hard")
                    break

    # ---------------------------------------------------------------- truth (hard)
    allowed_pool = " ".join([source_text or "", *(canon.locked_claims if canon else []),
                             *(canon.we_say if canon else []), canon.one_liner if canon else "",
                             canon.cta if canon else "", *extra_allowed_numbers])
    for n in _numbers(body):
        if n.rstrip("%") not in allowed_pool:
            add("fabricated-number",
                f"the figure \"{n}\" does not appear in the canon or the brief. Never invent numbers "
                "in public text: remove it or say it in words.", n, "hard")

    if not (canon and canon.allow_first_person_experience):
        for rx in _FABRICATED_EXPERIENCE:
            m = rx.search(body)
            if m:
                add("fabricated-experience",
                    "claims first-hand experience the brand owner did not supply. First person is for "
                    "opinion (\"my read is\"), never for what they have personally seen or done. "
                    f"Rewrite as a view rather than a memory. Remove: {_quote(m.group(0))}", m.group(0), "hard")
                break

    # ---------------------------------------------------------------- shape (soft)
    for op in _AGREE_OPENERS:
        if re.match(r"^\s*" + re.escape(op), body, re.I):
            add("agreement-opener", f"opens on a stock agreement phrase \"{op}\". Lead with the idea instead: {_quote(first)}", op)
            break

    for ph in _FILLER:
        if ph in low:
            add("filler", f"banned filler phrase \"{ph}\"", ph)

    for rx in _ANTITHESIS:
        m = rx.search(body)
        if m:
            add("antithesis", f"an \"X is not A, it is B\" antithesis; state the claim directly: {_quote(m.group(0))}", m.group(0))
            break

    m = _STACCATO.search(body)
    if m:
        add("staccato", f"the \"Not X. Y.\" staccato fragment device; write it as one plain sentence: {_quote(m.group(0))}", m.group(0))

    if _HOOK_COLON.match(body):
        add("hook-colon", f"a colon right after the opening hook: {_quote(first)}", first)

    m = _RULE_OF_THREE.search(body)
    if m:
        add("rule-of-three", f"three parallel items, cut to two: {_quote(m.group(0))}", m.group(0))

    for rx, label in _LEAK:
        m = rx.search(body)
        if m:
            add("instruction-leak", f"{label}. Cut the announcement and start at the claim: {_quote(m.group(0))}", m.group(0))

    if _MAXIM_UNTIL.search(body):
        add("maxim-until", f"the \"X works until Y\" aphorism shape: {_quote(first)}", first)
    m = _MAXIM_PARALLEL.search(body)
    if m:
        add("maxim-parallel", f"a balanced \"X handles the how while Y handles the should\" construction, which reads as a plaque rather than a person: {_quote(m.group(0))}", m.group(0))

    m = _LOOSE_HEDGE.search(body)
    if m:
        add("formula-hedge", f"a hedge that softens the claim to nothing: {_quote(m.group(0))}", m.group(0))
    for rx, tag, msg in _FORMULA:
        m = rx.search(body)
        if m:
            add(tag, f"{msg}: {_quote(m.group(0))}", m.group(0))

    if "—" in body:
        add("em-dash", "contains an em dash; use a period and a new sentence", "—")
    if "–" in body:
        add("en-dash", "contains an en dash", "–")

    # ---------------------------------------------------------------- length (soft)
    budget = None
    if canon and canon.max_words.get(channel):
        budget = canon.max_words[channel]
    elif kind == "comment":
        budget = DEFAULT_MAX_WORDS["comment"]
    else:
        budget = DEFAULT_MAX_WORDS.get(channel)
    if budget and words > budget:
        add("too-long", f"too long for {channel}: {words} words against a budget of {budget}. Make one point and stop.", str(words))

    # ---------------------------------------------------------------- comment-only (soft)
    if kind == "comment":
        for rules, tag, msg in (
            (_FAMILIARITY, "familiarity", "implies the author follows or has been watching this person. Congratulate the thing announced, not an imagined history with it"),
            (_UNEARNED_VERDICT, "verdict", "passes a verdict on work the author has not seen. Be glad for them, do not grade them"),
            (_THIRD_PARTY, "third-party-congrats", "congratulates someone other than the person being replied to"),
            (_INFLATION, "inflation", "rates the size of a stranger's news; say the plain congratulation and stop"),
            (_BORROWED, "borrowed-phrase", "reuses a stock exemplar phrase; say something that only fits this post"),
        ):
            for rx in rules:
                m = rx.search(body)
                if m:
                    add(tag, f"{msg}. Remove: {_quote(m.group(0))}", m.group(0))
                    break

    # ---------------------------------------------------------------- cta (soft)
    if canon and canon.cta and channel in ("newsletter", "email", "blog"):
        if normalise(canon.cta).lower() not in low:
            add("missing-cta", f"long-form piece without the brand's standing call to action: {_quote(canon.cta)}", canon.cta)

    # de-dupe by message, keep order
    seen: set[str] = set()
    uniq: list[GateViolation] = []
    for v in V:
        if v.message not in seen:
            seen.add(v.message)
            uniq.append(v)
    res.violations = uniq
    res.clean = not uniq
    res.ok = not any(v.severity == "hard" for v in uniq)
    return res


def rewrite_prompt(text: str, result: GateResult, canon: Optional[VoiceCanon] = None) -> str:
    """The repair instruction for an LLM. Port of the JS rewrite prompt, with the
    author-specific lines made brand-neutral. Describes requirements; never
    demonstrates them with a phrase the model could paste (the instruction-leak
    lesson)."""
    problems = "\n".join(f"{i + 1}. {v.message}" for i, v in enumerate(result.violations))
    brand = ""
    if canon is not None:
        bits = []
        if canon.tone:
            bits.append("Tone words for this brand: " + ", ".join(canon.tone) + ".")
        if canon.we_never_say:
            bits.append("Never use: " + "; ".join(canon.we_never_say) + ".")
        if canon.locked_claims:
            bits.append("If you keep any of these claims, reproduce them exactly: " + " | ".join(canon.locked_claims))
        brand = "\n".join(bits) + "\n"
    return (
        "Below is a short piece of public text written in a brand's voice, and a list of specific "
        "problems a checker found.\n\n"
        "Rewrite it fixing ONLY those problems. Every problem quotes the exact text at fault. Fix all of them.\n"
        "Keep the point, the register and the length. Do not make it more formal or more polished.\n"
        "Do not add new claims, new figures, or anything about the author that the brief does not state.\n"
        "Shorter is better than longer. Make one point. First person is for opinion, never for invented memories.\n"
        "Do not announce what kind of piece this is; start at the claim.\n"
        + brand +
        "\n=== PROBLEMS ===\n" + problems + "\n\n"
        "=== CONSTRAINTS YOUR OUTPUT MUST ALSO SATISFY ===\n"
        "- no em dash and no en dash anywhere\n"
        "- no stock agreement opener\n"
        "- no \"usually\" or \"typically\" as a hedge, no \"The real/biggest X\" or \"Most <group>\" opener\n"
        "Fixing one problem must not introduce another.\n\n"
        "=== TEXT ===\n" + text + "\n\n"
        "Return ONLY the rewritten text. No quotes around it, no preamble, no explanation."
    )
