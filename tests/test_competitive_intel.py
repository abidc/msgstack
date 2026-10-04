"""Competitor document import, gap analysis, and battlecard auto-sharpen."""

import os
import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from src.models import CanonDomain, CanonEntry, DomainStatus, EntryStatus, GroundingType, SectionType
from src.pipeline.competitive_intel import analyze_competitive_gap, extract_competitor_claims, sharpen_battlecard


@pytest.fixture
def store(tmp_path):
    import src.store as store_mod
    from src.store import Store
    s = Store(str(tmp_path / "competitive_intel_test.db"))
    s.init()
    prev = store_mod._store_instance
    store_mod._store_instance = s
    yield s
    store_mod._store_instance = prev


@pytest.fixture
def competitor_domain(store):
    domain = CanonDomain(name="RivalCo", grounding_type=GroundingType.COMPETITIVE_BRIEF, status=DomainStatus.ACTIVE)
    store.upsert_canon_domain(domain)
    return domain


@pytest.fixture
def our_domain(store):
    domain = CanonDomain(name="Us", grounding_type=GroundingType.MESSAGE_HOUSE, status=DomainStatus.ACTIVE)
    store.upsert_canon_domain(domain)
    return domain


DOCUMENT = (
    "RivalCo Platform Overview. RivalCo processes payments in under 48 hours. "
    "Our support team is only available during business hours."
)


def _mock_client(claims):
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=json.dumps({"claims": claims})))
    ]
    return client


def test_extract_verbatim_claim_is_kept(store, competitor_domain):
    client = _mock_client([{"quote": "RivalCo processes payments in under 48 hours.", "type": "strength"}])
    with patch("src.config.llm_client", return_value=client):
        entries = extract_competitor_claims(DOCUMENT, "RivalCo", competitor_domain.id, store, client=client)
    assert len(entries) == 1
    assert entries[0].content == "RivalCo processes payments in under 48 hours."
    assert entries[0].section_type == SectionType.COMPETITOR_STRENGTH.value
    assert entries[0].source_chunk_id.startswith("chars:")
    start, end = (int(x) for x in entries[0].source_chunk_id.removeprefix("chars:").split("-"))
    assert DOCUMENT[start:end] == entries[0].content


def test_extract_discards_paraphrased_claim(store, competitor_domain):
    client = _mock_client([{"quote": "RivalCo is slow to pay out.", "type": "weakness"}])
    entries = extract_competitor_claims(DOCUMENT, "RivalCo", competitor_domain.id, store, client=client)
    assert entries == []


def test_extract_rejects_non_competitive_brief_domain(store, our_domain):
    client = _mock_client([])
    with pytest.raises(ValueError):
        extract_competitor_claims(DOCUMENT, "RivalCo", our_domain.id, store, client=client)


def test_gap_analysis_creates_contradicts_edge_for_overlapping_claim(store, competitor_domain, our_domain):
    our_entry = CanonEntry(canon_domain_id=our_domain.id, section_type=SectionType.PROOF_POINT, priority=1,
                            content="We process payments in under 2 hours, 24x faster than RivalCo.",
                            status=EntryStatus.APPROVED)
    store.upsert_canon_entry(our_entry)
    their_entry = CanonEntry(canon_domain_id=competitor_domain.id, section_type=SectionType.COMPETITOR_STRENGTH, priority=1,
                              content="RivalCo processes payments in under 48 hours.", status=EntryStatus.DRAFT)
    store.upsert_canon_entry(their_entry)

    result = analyze_competitive_gap(our_domain.id, competitor_domain.id, store)

    assert result["edges_created"] == 1
    edges = store.list_edges(src_id=str(their_entry.id))
    assert len(edges) == 1
    assert edges[0]["provenance"] == "RivalCo processes payments in under 48 hours."


def test_gap_analysis_flags_uncovered_claim_as_differentiated(store, competitor_domain, our_domain):
    their_entry = CanonEntry(canon_domain_id=competitor_domain.id, section_type=SectionType.COMPETITOR_STRENGTH, priority=1,
                              content="RivalCo offers astrology-based fraud detection.", status=EntryStatus.DRAFT)
    store.upsert_canon_entry(their_entry)

    result = analyze_competitive_gap(our_domain.id, competitor_domain.id, store)

    assert result["edges_created"] == 0
    assert len(result["differentiated"]) == 1
    assert "uncovered gap" in result["differentiated"][0]["note"]


def test_sharpen_battlecard_assembles_counter_messaging_from_graph(store, competitor_domain, our_domain):
    our_entry = CanonEntry(canon_domain_id=our_domain.id, section_type=SectionType.PROOF_POINT, priority=1,
                            content="We process payments in under 2 hours.", status=EntryStatus.LOCKED,
                            content_tier="tier_1_locked")
    store.upsert_canon_entry(our_entry)
    their_strength = CanonEntry(canon_domain_id=competitor_domain.id, section_type=SectionType.COMPETITOR_STRENGTH,
                                 priority=1, content="RivalCo processes payments in under 48 hours.", status=EntryStatus.DRAFT)
    store.upsert_canon_entry(their_strength)
    their_weakness = CanonEntry(canon_domain_id=competitor_domain.id, section_type=SectionType.COMPETITOR_WEAKNESS,
                                 priority=1, content="Support is business-hours only.", status=EntryStatus.DRAFT)
    store.upsert_canon_entry(their_weakness)

    analyze_competitive_gap(our_domain.id, competitor_domain.id, store)
    card = sharpen_battlecard("RivalCo", competitor_domain.id, our_domain.id, store)

    assert card["competitor"] == "RivalCo"
    assert "We process payments in under 2 hours." in card["our_strengths"]
    assert "Support is business-hours only." in card["their_weaknesses"]
    assert any("RivalCo processes payments in under 48 hours." in m for m in card["counter_messaging"])
    assert "We process payments in under 2 hours." in card["proof_points"]


# ── API endpoint wiring ──────────────────────────────────────────────────────

def test_competitive_intel_api_endpoints_wire_through(tmp_path):
    import src.web_app as web_app_module
    from src.store import Store
    from fastapi.testclient import TestClient

    test_store = Store(str(tmp_path / "competitive_intel_api_test.db"))
    test_store.init()

    our_domain = CanonDomain(name="Us", grounding_type=GroundingType.MESSAGE_HOUSE, status=DomainStatus.ACTIVE)
    test_store.upsert_canon_domain(our_domain)
    our_entry = CanonEntry(canon_domain_id=our_domain.id, section_type=SectionType.PROOF_POINT, priority=1,
                            content="We process payments in under 2 hours.", status=EntryStatus.APPROVED)
    test_store.upsert_canon_entry(our_entry)

    competitor_domain = CanonDomain(name="RivalCo", grounding_type=GroundingType.COMPETITIVE_BRIEF, status=DomainStatus.ACTIVE)
    test_store.upsert_canon_domain(competitor_domain)

    old_store = web_app_module.store
    web_app_module.store = test_store
    client = TestClient(web_app_module.app)
    try:
        client_mock = _mock_client([{"quote": "RivalCo processes payments in under 48 hours.", "type": "strength"}])
        with patch("src.config.llm_client", return_value=client_mock):
            resp = client.post("/api/competitive/extract", json={
                "document_text": DOCUMENT, "competitor_name": "RivalCo", "domain_id": str(competitor_domain.id),
            })
        assert resp.status_code == 200, resp.text
        assert resp.json()["extracted"] == 1

        resp2 = client.post("/api/competitive/gap-analysis", json={
            "our_domain_id": str(our_domain.id), "competitor_domain_id": str(competitor_domain.id),
        })
        assert resp2.status_code == 200, resp2.text
        assert resp2.json()["edges_created"] == 1

        resp3 = client.post("/api/competitive/battlecard", json={
            "competitor_name": "RivalCo", "competitor_domain_id": str(competitor_domain.id), "our_domain_id": str(our_domain.id),
        })
        assert resp3.status_code == 200, resp3.text
        assert resp3.json()["competitor"] == "RivalCo"
    finally:
        web_app_module.store = old_store
