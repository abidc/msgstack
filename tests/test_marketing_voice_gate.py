"""Deterministic voice gate (src/marketing/voice_gate.py) — rules ported from voice-lint/lint_template.js."""

from uuid import uuid4

from src.marketing.models import VoiceCanon
from src.marketing.voice_gate import GATE_VERSION, lint, rewrite_prompt

BRAND = uuid4()


def _canon(**kw) -> VoiceCanon:
    base = dict(
        brand_id=BRAND, one_liner="Coaching for engineers stepping into leadership.",
        audience="A newly promoted engineering manager.", tone=["plain", "direct", "warm"],
        we_never_say=["synergy", "unlock your potential"], locked_claims=["Clients finish the program in 12 weeks."],
        topics=["delegation", "feedback"], off_limits=["layoffs"], cta="Reply and tell me what you are working on.",
    )
    base.update(kw)
    return VoiceCanon(**base)


CLEAN = ("Delegation gets easier when you stop grading the method and start grading the result. "
         "Say what done looks like, then get out of the way. Reply and tell me what you are working on.")


def test_clean_text_passes_with_no_violations():
    r = lint(CLEAN, _canon(), channel="linkedin")
    assert r.clean and r.ok
    assert r.violations == []
    assert r.version == GATE_VERSION
    assert r.words > 10


def test_empty_text_is_a_hard_violation():
    r = lint("", _canon())
    assert not r.ok and r.rules == ["empty"]


def test_em_and_en_dash_are_soft():
    r = lint(CLEAN.replace("result.", "result — every time.") + " Range 2–3.", _canon(),
             source_text="2 3")
    assert "em-dash" in r.rules and "en-dash" in r.rules
    assert r.ok and not r.clean  # soft only


def test_antithesis_both_directions():
    fwd = lint("It's not a tooling problem, it's a judgment problem. " + CLEAN, _canon())
    rev = lint("This is an operational overhaul, not a new plugin. " + CLEAN, _canon())
    assert "antithesis" in fwd.rules and "antithesis" in rev.rules


def test_formula_openers_and_hedges():
    most = lint("Most managers never learn to delegate. " + CLEAN, _canon())
    sup = lint("The real problem is nobody defines done. " + CLEAN, _canon())
    hedge = lint("Managers usually grade the method. " + CLEAN, _canon())
    assert "formula-most" in most.rules
    assert "formula-superlative" in sup.rules
    assert "formula-hedge" in hedge.rules


def test_agreement_opener_filler_and_leak():
    r = lint("Totally agree. Here's the thing: the less comfortable version is that nobody defines done. " + CLEAN, _canon())
    assert {"agreement-opener", "filler", "instruction-leak"} <= set(r.rules)


def test_fabricated_number_is_hard_unless_in_brief_or_canon():
    text = "We cut handoff time by 37% last quarter. " + CLEAN
    bad = lint(text, _canon())
    assert not bad.ok and "fabricated-number" in bad.rules
    ok = lint(text, _canon(), source_text="Handoff time fell 37% in Q3 per the ops dashboard.")
    assert "fabricated-number" not in ok.rules
    # a number inside a locked claim, reproduced verbatim, is allowed
    verb = lint("Clients finish the program in 12 weeks. " + CLEAN, _canon())
    assert "fabricated-number" not in verb.rules and verb.ok


def test_locked_claim_paraphrase_is_hard():
    r = lint("Most of our clients wrap up in about 12 weeks. " + CLEAN, _canon())
    assert not r.ok and "locked-claim-paraphrase" in r.rules
    span = next(v for v in r.violations if v.rule == "locked-claim-paraphrase")
    assert "12" in span.span and "verbatim" in span.message


def test_banned_phrase_and_off_limits_topic_are_hard():
    r = lint("Unlock your potential after the layoffs. " + CLEAN, _canon())
    hard = {v.rule for v in r.hard}
    assert {"banned-phrase", "off-limits-topic"} <= hard
    assert not r.ok


def test_fabricated_experience_hard_unless_canon_allows():
    text = "I've seen this play out with a dozen teams. " + CLEAN
    r = lint(text, _canon())
    assert "fabricated-experience" in {v.rule for v in r.hard}
    r2 = lint(text, _canon(allow_first_person_experience=True))
    assert "fabricated-experience" not in r2.rules


def test_comment_only_rules_apply_only_to_comments():
    text = "Congrats, been watching this one and it's well earned. What an achievement."
    post = lint(text, _canon(), kind="post")
    comment = lint(text, _canon(), kind="comment")
    assert "familiarity" not in post.rules
    assert {"familiarity", "verdict", "inflation"} <= set(comment.rules)


def test_length_budget_per_channel_and_canon_override():
    long = " ".join(["word"] * 70) + "."
    assert "too-long" in lint(long, _canon(), channel="x").rules          # 60-word default for x
    assert "too-long" not in lint(long, _canon(), channel="linkedin").rules
    assert "too-long" in lint(long, _canon(max_words={"linkedin": 50}), channel="linkedin").rules


def test_missing_cta_is_soft_and_long_form_only():
    body = "Delegation gets easier when you stop grading the method and start grading the result."
    assert "missing-cta" in lint(body, _canon(), channel="newsletter").rules
    assert "missing-cta" not in lint(body, _canon(), channel="linkedin").rules


def test_rewrite_prompt_quotes_each_problem_and_brand_rules():
    r = lint("Totally agree — unlock your potential.", _canon())
    p = rewrite_prompt("Totally agree — unlock your potential.", r, _canon())
    assert "=== PROBLEMS ===" in p and "=== TEXT ===" in p
    for i in range(1, len(r.violations) + 1):
        assert f"{i}. " in p
    assert "Never use: synergy" in p
    assert "Clients finish the program in 12 weeks." in p


def test_violations_are_deduplicated_and_quote_spans():
    r = lint("Here's the thing. Here's the thing again. " + CLEAN, _canon())
    assert r.rules.count("filler") == 1
    assert all(v.message for v in r.violations)
