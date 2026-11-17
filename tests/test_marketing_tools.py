"""End-to-end behaviour of the marketing tools: intake → generate → gate → approve/reject → schedule → results.

Runs entirely offline: the template path needs no LLM, and the LLM path is exercised
with a fake callable.
"""

import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from src.marketing import tools
from src.marketing.store import MarketingStore, NotFound, set_marketing_store

FULL = dict(
    name="The Climb with Abid",
    one_liner="Coaching for engineers stepping into leadership.",
    audience="A newly promoted engineering manager who still codes.",
    tone=["plain", "direct", "warm"],
    we_never_say=["synergy", "unlock your potential"],
    locked_claims=["Clients finish the program in 12 weeks."],
    topics=["delegation", "feedback", "saying no"],
    off_limits=["layoffs"],
    cta="Reply and tell me what you are working on.",
    example_posts=["Say what done looks like, then get out of the way."],
    owner="abid",
)


@pytest.fixture
def st(tmp_path):
    s = MarketingStore(f"sqlite:///{tmp_path / 'tools.db'}").init()
    set_marketing_store(s)
    yield s
    set_marketing_store(None)


def _brand(st, **over):
    data = {**FULL, **over}
    return tools.brand_intake(store=st, **data)["brand"]["id"]


# ------------------------------------------------------------------ intake

def test_partial_intake_reports_missing_and_next_questions(st):
    out = tools.brand_intake(name="Luna Pilates", one_liner="Pilates for desk workers.", store=st)
    canon = out["canon"]
    assert canon["version"] == 1 and canon["completeness"] < 50
    assert "audience" in canon["missing"] and canon["ready_for_generation"] is False
    assert len(canon["next_questions"]) == 3
    assert canon["next_questions"][0] == tools.INTAKE_QUESTIONS["audience"]


def test_intake_requires_a_name(st):
    with pytest.raises(ValueError):
        tools.brand_intake(name="  ", store=st)


def test_update_canon_appends_version_and_unblocks_generation(st):
    bid = tools.brand_intake(name="Luna", one_liner="Pilates for desk workers.", store=st)["brand"]["id"]
    blocked = tools.generate_week(bid, store=st, use_llm=False)
    assert blocked["blocked"] == "canon_not_ready" and blocked["generated"] == 0
    out = tools.update_voice_canon(bid, store=st, audience="A tired analyst", tone=["calm"],
                                   topics=["posture", "breaks"], cta="Book a trial class.")
    assert out["canon"]["version"] == 2 and out["canon"]["ready_for_generation"] is True
    with pytest.raises(ValueError):
        tools.update_voice_canon(bid, store=st, colour="blue")


def test_list_brands_shows_completeness(st):
    _brand(st)
    tools.brand_intake(name="Other", workspace_id="agency-1", store=st)
    all_ = tools.list_brands(store=st)
    assert all_["count"] == 2 and all_["brands"][0]["completeness"] > all_["brands"][1]["completeness"]
    assert tools.list_brands("agency-1", store=st)["count"] == 1


# ------------------------------------------------------------------ gate tool

def test_check_voice_reports_hard_and_soft(st):
    bid = _brand(st)
    r = tools.check_voice(bid, "Totally agree. We boosted output 40% with synergy.", store=st)
    assert r["ok"] is False
    assert {"fabricated-number", "banned-phrase"} <= {v["rule"] for v in r["hard"]}
    assert "agreement-opener" in {v["rule"] for v in r["soft"]}
    assert r["canon_version"] == 1


# ------------------------------------------------------------------ generation

def test_generate_week_template_mode_fills_posting_days_and_rotates_topics(st):
    bid = _brand(st)
    out = tools.generate_week(bid, channel="linkedin", start_date="2026-11-16", count=3, store=st, use_llm=False)
    assert out["mode"] == "template" and out["generated"] == 3
    dates = [i["slot_date"] for i in out["items"]]
    assert dates == ["2026-11-16", "2026-11-18", "2026-11-20"]  # Mon/Wed/Fri
    assert [i["topic"] for i in out["items"]] == ["delegation", "feedback", "saying no"]
    assert all(i["generated_by"] == "template" for i in out["items"])
    assert all(i["status"] == "draft" for i in out["items"])  # template drafts are clean against their own canon
    # next week rotates onward instead of repeating topic 1
    nxt = tools.generate_week(bid, channel="linkedin", start_date="2026-11-23", count=1, store=st, use_llm=False)
    assert nxt["items"][0]["topic"] == "delegation"  # 3 covered -> offset 3 -> wraps to first


def test_generate_week_respects_weekly_quota(st):
    bid = _brand(st, weekly_quota={"linkedin": 2})
    first = tools.generate_week(bid, channel="linkedin", start_date="2026-11-16", count=5, store=st, use_llm=False)
    assert first["generated"] == 2 and first["requested"] == 5
    again = tools.generate_week(bid, channel="linkedin", start_date="2026-11-17", count=1, store=st, use_llm=False)
    assert again["blocked"] == "weekly_quota_reached" and again["open"] == 2
    # a different channel has its own quota
    other = tools.generate_week(bid, channel="newsletter", start_date="2026-11-16", count=1, store=st, use_llm=False)
    assert other["generated"] == 1
    with pytest.raises(ValueError):
        tools.generate_week(bid, count=0, store=st, use_llm=False)


def test_generate_week_llm_path_gates_and_rewrites_once(st):
    bid = _brand(st)
    calls = []

    def fake_llm(system, user):
        calls.append((system, user))
        if "=== PROBLEMS ===" in user:  # the rewrite call
            return "Delegation gets easier when you grade the result. Reply and tell me what you are working on."
        return "Most managers never delegate — it's not laziness, it's fear. Reply and tell me what you are working on."

    fake_llm.model_name = "fake-1"
    out = tools.generate_week(bid, channel="linkedin", start_date="2026-11-16", count=1, store=st, llm=fake_llm)
    item = out["items"][0]
    assert out["mode"] == "llm" and item["generated_by"] == "llm:fake-1"
    assert item["rewrite_count"] == 1 and len(calls) == 2
    assert item["gate"]["clean"] is True and item["status"] == "draft"
    assert "grade the result" in item["body"]
    # the system prompt carries the canon but never pastes a usable opener
    system = calls[0][0]
    assert "Clients finish the program in 12 weeks." in system and "never uses: synergy" in system


def test_generate_week_llm_hard_violation_lands_as_needs_rework(st):
    bid = _brand(st)

    def stubborn(system, user):
        return "We tripled revenue to 300% with synergy. Reply and tell me what you are working on."

    out = tools.generate_week(bid, channel="x", start_date="2026-11-16", count=1, store=st, llm=stubborn)
    item = out["items"][0]
    assert item["status"] == "needs_rework" and out["needs_rework"] == 1
    assert {"fabricated-number", "banned-phrase"} <= {v["rule"] for v in item["gate"]["hard"]}


def test_rewrite_failure_keeps_original_draft(st):
    bid = _brand(st)
    n = {"i": 0}

    def flaky(system, user):
        n["i"] += 1
        if n["i"] == 1:
            return "Totally agree. Delegation gets easier. Reply and tell me what you are working on."
        raise RuntimeError("provider down")

    out = tools.generate_week(bid, channel="linkedin", start_date="2026-11-16", count=1, store=st, llm=flaky)
    item = out["items"][0]
    assert item["body"].startswith("Totally agree") and item["rewrite_count"] == 0
    assert "agreement-opener" in item["gate"]["rules"] and item["status"] == "draft"


# ------------------------------------------------------------------ queue + decisions

def _one_draft(st, bid, body=None, channel="linkedin"):
    if body is None:
        out = tools.generate_week(bid, channel=channel, start_date="2026-11-16", count=1, store=st, use_llm=False)
    else:
        out = tools.generate_week(bid, channel=channel, start_date="2026-11-16", count=1, store=st,
                                  llm=lambda s, u: body)
    return out["items"][0]["id"]


def test_approve_creates_schedule_and_moves_item(st):
    bid = _brand(st)
    cid = _one_draft(st, bid)
    assert tools.review_queue(bid, store=st)["count"] == 1
    res = tools.approve_content(bid, cid, decided_by="abid", destination="buffer", store=st)
    assert res["approved"] is True
    assert res["schedule"]["destination"] == "buffer"
    assert res["schedule"]["publish_at"].startswith("2026-11-16T09:00")
    assert tools.review_queue(bid, store=st)["count"] == 0
    assert tools.review_queue(bid, status="approved", store=st)["count"] == 1
    with pytest.raises(ValueError):
        tools.approve_content(bid, cid, store=st)  # already approved


def test_approve_refuses_hard_violations_without_override(st):
    bid = _brand(st)
    cid = _one_draft(st, bid, body="We grew 400% with synergy. Reply and tell me what you are working on.")
    res = tools.approve_content(bid, cid, decided_by="abid", store=st)
    assert res["approved"] is False and res["blocked"] == "hard_violations"
    with pytest.raises(ValueError):
        tools.approve_content(bid, cid, decided_by="abid", override=True, store=st)  # no reason
    ok = tools.approve_content(bid, cid, decided_by="abid", override=True, reason="figure verified in Stripe", store=st)
    assert ok["approved"] is True and ok["approval"]["override_hard"] is True


def test_approve_with_edited_body_regates(st):
    bid = _brand(st)
    cid = _one_draft(st, bid, body="We grew 400% with synergy. Reply and tell me what you are working on.")
    ok = tools.approve_content(bid, cid, decided_by="abid", store=st,
                               edited_body="We grew a lot this year. Reply and tell me what you are working on.")
    assert ok["approved"] is True and ok["approval"]["override_hard"] is False
    item = tools.review_queue(bid, status="approved", store=st)["items"][0]
    assert item["gate"]["ok"] is True and item["generated_by"].endswith("+edited")


def test_reject_requires_reason_and_records_it(st):
    bid = _brand(st)
    cid = _one_draft(st, bid)
    with pytest.raises(ValueError):
        tools.reject_content(bid, cid, reason="", store=st)
    res = tools.reject_content(bid, cid, reason="not my voice", decided_by="abid", store=st)
    assert res["rejected"] and res["approval"]["reason"] == "not my voice"
    assert tools.review_queue(bid, status="rejected", store=st)["count"] == 1
    with pytest.raises(ValueError):
        tools.mark_published(bid, cid, store=st)


# ------------------------------------------------------------------ results

def test_mark_published_and_results_readback(st):
    bid = _brand(st)
    cid = _one_draft(st, bid)
    tools.approve_content(bid, cid, decided_by="abid", publish_at="2026-11-16T09:00:00", store=st)
    before = tools.get_results(bid, store=st)
    assert before["published_count"] == 0 and before["scheduled_count"] == 1
    pub = tools.mark_published(bid, cid, external_ref="https://www.linkedin.com/posts/x", published_at="2026-11-16T09:03:00",
                               metrics={"impressions": 1200}, store=st)
    assert pub["published"] is True
    after = tools.get_results(bid, store=st)
    assert after["published_count"] == 1 and after["scheduled_count"] == 0
    row = after["published"][0]
    assert row["approved_by"] == "abid" and row["external_ref"].endswith("/x")
    assert row["metrics"] == {"impressions": 1200} and row["gate_clean"] is True
    assert tools.get_results(bid, since="2026-11-17T00:00:00", store=st)["published_count"] == 0


# ------------------------------------------------------------------ tenancy

def test_cross_brand_access_is_refused(st):
    a = _brand(st)
    b = _brand(st, name="Other Brand")
    cid = _one_draft(st, a)
    with pytest.raises(NotFound):
        tools.approve_content(b, cid, store=st)
    with pytest.raises(NotFound):
        tools.reject_content(b, cid, reason="x", store=st)
    with pytest.raises(NotFound):
        tools.get_brand("00000000-0000-0000-0000-000000000000", store=st)
    with pytest.raises(ValueError):
        tools.get_brand("not-a-uuid", store=st)
    assert tools.review_queue(b, store=st)["count"] == 0


# ------------------------------------------------------------------ MCP wrappers

def test_mcp_tool_wrappers_delegate_to_tools(st):
    from src import server
    out = server.brand_intake(**FULL)
    bid = out["brand"]["id"]
    gen = server.generate_week(bid, channel="linkedin", start_date="2026-11-16", count=1, use_llm=False)
    cid = gen["items"][0]["id"]
    assert server.review_queue(bid)["count"] == 1
    assert server.check_voice(bid, "Totally agree.")["ok"] is True
    assert server.approve_content(bid, cid, decided_by="abid")["approved"] is True
    assert server.mark_published(bid, cid, external_ref="ref-1")["published"] is True
    assert server.get_results(bid)["published_count"] == 1
    assert server.list_brands()["count"] == 1
    assert server.update_voice_canon(bid, notes="v2")["canon"]["version"] == 2
    assert server.get_brand(bid)["canon"]["notes"] == "v2"
    with pytest.raises(ValueError):
        server.reject_content(bid, cid, reason="x")  # already published
