"""Alignment/drift trend dashboard: Canon Health Score tracked over time, not
just the existing point-in-time gauge."""

import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from src.models import CanonDomain, DomainStatus, GroundingType


@pytest.fixture
def store(tmp_path):
    import src.store as store_mod
    from src.store import Store
    s = Store(str(tmp_path / "health_trend_test.db"))
    s.init()
    prev = store_mod._store_instance
    store_mod._store_instance = s
    yield s
    store_mod._store_instance = prev


@pytest.fixture
def domain(store):
    d = CanonDomain(name="Acme", grounding_type=GroundingType.MESSAGE_HOUSE, status=DomainStatus.ACTIVE)
    store.upsert_canon_domain(d)
    return d


def test_record_snapshot_then_read_trend(store, domain):
    store.record_health_snapshot(domain.id, completeness_score=40)
    trend = store.get_health_trend(domain.id)
    assert len(trend) == 1
    assert trend[0]["completeness_score"] == 40


def test_same_day_calls_upsert_not_duplicate(store, domain):
    store.record_health_snapshot(domain.id, completeness_score=40)
    store.record_health_snapshot(domain.id, completeness_score=65)
    trend = store.get_health_trend(domain.id)
    assert len(trend) == 1  # one row per domain per day, not one per call
    assert trend[0]["completeness_score"] == 65  # latest wins


def test_different_days_produce_separate_points(store, domain):
    import src.store as store_mod

    with patch.object(store_mod, "_now", return_value=datetime(2026, 1, 1)):
        store.record_health_snapshot(domain.id, completeness_score=30)
    with patch.object(store_mod, "_now", return_value=datetime(2026, 1, 2)):
        store.record_health_snapshot(domain.id, completeness_score=55)

    trend = store.get_health_trend(domain.id)
    assert [t["day"] for t in trend] == ["2026-01-01", "2026-01-02"]
    assert [t["completeness_score"] for t in trend] == [30, 55]


def test_alignment_score_tracked_independently_of_completeness(store, domain):
    store.record_health_snapshot(domain.id, completeness_score=70)
    store.record_health_snapshot(domain.id, alignment_score=85)
    trend = store.get_health_trend(domain.id)
    assert len(trend) == 1
    assert trend[0]["completeness_score"] == 70
    assert trend[0]["alignment_score"] == 85


def test_mcp_completeness_check_records_a_snapshot(store, domain):
    from src.models import CanonEntry, EntryStatus, SectionType
    entry = CanonEntry(canon_domain_id=domain.id, section_type=SectionType.HEADLINE, priority=1,
                        content="A headline", status=EntryStatus.APPROVED)
    store.upsert_canon_entry(entry)

    import src.server as server_mod
    from src.server import check_canon_completeness
    old_get_store = server_mod.get_store
    server_mod.get_store = lambda: store
    try:
        result = check_canon_completeness(domain_id=str(domain.id))
    finally:
        server_mod.get_store = old_get_store

    assert "score" in result
    trend = store.get_health_trend(domain.id)
    assert len(trend) == 1
    assert trend[0]["completeness_score"] == result["score"]


def test_health_trend_api_endpoint(tmp_path):
    import src.web_app as web_app_module
    from src.store import Store
    from fastapi.testclient import TestClient

    test_store = Store(str(tmp_path / "health_trend_api_test.db"))
    test_store.init()
    d = CanonDomain(name="Acme", grounding_type=GroundingType.MESSAGE_HOUSE, status=DomainStatus.ACTIVE)
    test_store.upsert_canon_domain(d)

    import src.store as store_mod
    with patch.object(store_mod, "_now", return_value=datetime(2026, 1, 1)):
        test_store.record_health_snapshot(d.id, completeness_score=80)
    with patch.object(store_mod, "_now", return_value=datetime(2026, 1, 2)):
        test_store.record_health_snapshot(d.id, completeness_score=45)

    old_store = web_app_module.store
    web_app_module.store = test_store
    client = TestClient(web_app_module.app)
    try:
        resp = client.get(f"/api/canon-domains/{d.id}/health-trend")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["trend"]) == 2
        assert body["degrading"] is True  # 45 < 80, score dropped
    finally:
        web_app_module.store = old_store


def test_health_trend_404_for_unknown_domain(tmp_path):
    import src.web_app as web_app_module
    from src.store import Store
    from fastapi.testclient import TestClient
    from uuid import uuid4

    test_store = Store(str(tmp_path / "health_trend_404_test.db"))
    test_store.init()
    old_store = web_app_module.store
    web_app_module.store = test_store
    client = TestClient(web_app_module.app)
    try:
        resp = client.get(f"/api/canon-domains/{uuid4()}/health-trend")
        assert resp.status_code == 404
    finally:
        web_app_module.store = old_store
