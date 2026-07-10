"""Tests for the alias and backward compatibility layers for both FastAPI and MCP server."""

import os
import json
import warnings
from uuid import UUID, uuid4
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

# Ensure key env vars are set
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")


@pytest.fixture
def test_setup(tmp_path):
    """Setup a temporary database and app context."""
    import src.web_app as web_app_module
    from src.store import Store
    from src.models import CanonDomain, CanonEntry, Persona, SectionType, EntryStatus, DomainStatus

    db_path = tmp_path / "alias_compat_test.db"
    store = Store(str(db_path))
    store.init()

    # Seed one test domain
    domain = CanonDomain(
        name="Compatibility Test Brand",
        summary="A brand for compatibility testing.",
        positioning="Positioning statement for compat testing.",
        tagline="Compat Tagline",
        differentiation="Differentiated product solution.",
        status=DomainStatus.ACTIVE,
    )
    store.upsert_house(domain)

    # Seed one entry
    entry = CanonEntry(
        canon_domain_id=domain.id,
        section_type=SectionType.BENEFIT,
        priority=1,
        content="Seed entry content",
        status=EntryStatus.APPROVED,
        content_tier="tier_2_structured",
    )
    store.upsert_key_message(entry)

    # Seed one persona
    persona = Persona(
        canon_domain_id=domain.id,
        name="Compat Persona",
        description="A persona for compat test",
        pain_points=[" Slow deployment"],
    )
    store.upsert_persona(persona)

    # Patch the web app's store
    old_store = web_app_module.store
    web_app_module.store = store

    client = TestClient(web_app_module.app)

    yield store, client, domain, entry, persona

    web_app_module.store = old_store


# ── FastAPI Endpoint Alias Tests ─────────────────────────────────────────────

def test_canon_domains_endpoint_aliases(test_setup):
    _, client, domain, _, _ = test_setup

    # Test GET list
    resp1 = client.get("/api/canon-domains")
    assert resp1.status_code == 200
    assert any(h["id"] == str(domain.id) for h in resp1.json())

    resp2 = client.get("/api/houses")
    assert resp2.status_code == 200
    assert any(h["id"] == str(domain.id) for h in resp2.json())

    # Test GET detail
    resp3 = client.get(f"/api/canon-domains/{domain.id}")
    assert resp3.status_code == 200
    assert resp3.json()["name"] == domain.name

    resp4 = client.get(f"/api/houses/{domain.id}")
    assert resp4.status_code == 200
    assert resp4.json()["name"] == domain.name


def test_canon_entries_endpoints_aliases(test_setup):
    _, client, domain, entry, _ = test_setup

    # Test POST create with canon parameter
    resp_create_canon = client.post("/api/entries", json={
        "canon_domain_id": str(domain.id),
        "section_type": "headline",
        "content": "New headline content",
        "priority": 2
    })
    assert resp_create_canon.status_code == 200
    canon_id = resp_create_canon.json()["id"]

    # Test POST create with legacy parameter
    resp_create_legacy = client.post("/api/messages", json={
        "message_house_id": str(domain.id),
        "section_type": "headline",
        "content": "Legacy parameter content",
        "priority": 3
    })
    assert resp_create_legacy.status_code == 200
    legacy_id = resp_create_legacy.json()["id"]

    # Test PATCH update
    resp_update_canon = client.patch(f"/api/entries/{canon_id}", json={"content": "Updated headline content"})
    assert resp_update_canon.status_code == 200

    resp_update_legacy = client.patch(f"/api/messages/{legacy_id}", json={"content": "Updated legacy content"})
    assert resp_update_legacy.status_code == 200

    # Set tiers before approving (promotion gate requires content_tier)
    resp_tier_canon = client.patch(f"/api/entries/{canon_id}/tier", json={"content_tier": "tier_2_structured"})
    assert resp_tier_canon.status_code == 200
    resp_tier_legacy = client.patch(f"/api/messages/{legacy_id}/tier", json={"content_tier": "tier_3_grounded"})
    assert resp_tier_legacy.status_code == 200

    # Test PATCH status
    resp_status_canon = client.patch(f"/api/entries/{canon_id}/status", json={"status": "approved", "approved_by": "tester"})
    assert resp_status_canon.status_code == 200
    assert resp_status_canon.json()["status"] in ("approved", "EntryStatus.APPROVED")

    resp_status_legacy = client.patch(f"/api/messages/{legacy_id}/status", json={"status": "approved", "approved_by": "tester"})
    assert resp_status_legacy.status_code == 200

    # Test DELETE
    resp_del_canon = client.delete(f"/api/entries/{canon_id}")
    assert resp_del_canon.status_code == 200

    resp_del_legacy = client.delete(f"/api/messages/{legacy_id}")
    assert resp_del_legacy.status_code == 200


def test_canon_domain_sub_endpoints_aliases(test_setup):
    store, client, domain, entry, _ = test_setup

    # review / review-trail / staleness / snapshots / artifacts / heatmap / coverage / usage-stats
    for path in ["review", "staleness", "review-trail", "snapshots", "artifacts", "heatmap", "coverage", "usage-stats", "mark-reviewed", "review-log"]:
        # Test canon domain path
        if path == "review":
            resp = client.post(f"/api/canon-domains/{domain.id}/review?performed_by=test")
        elif path == "snapshots":
            resp = client.get(f"/api/canon-domains/{domain.id}/snapshots")
        elif path == "mark-reviewed":
            resp = client.post(f"/api/canon-domains/{domain.id}/mark-reviewed")
        else:
            resp = client.get(f"/api/canon-domains/{domain.id}/{path}")
        assert resp.status_code in (200, 201), f"Canon path failed for /{path}: {resp.content}"

        # Test legacy house path
        if path == "review":
            resp_leg = client.post(f"/api/houses/{domain.id}/review?performed_by=test")
        elif path == "snapshots":
            resp_leg = client.get(f"/api/houses/{domain.id}/snapshots")
        elif path == "mark-reviewed":
            resp_leg = client.post(f"/api/houses/{domain.id}/mark-reviewed")
        else:
            resp_leg = client.get(f"/api/houses/{domain.id}/{path}")
        assert resp_leg.status_code in (200, 201), f"Legacy path failed for /{path}: {resp_leg.content}"


# ── MCP Tool Alias Tests ──────────────────────────────────────────────────────

@pytest.fixture
def mock_mcp_store(tmp_path):
    """Setup a store and patch server-level functions."""
    from src.store import Store
    from src.models import CanonDomain, CanonEntry, SectionType, DomainStatus, EntryStatus
    import src.server as server_module

    db_path = tmp_path / "mcp_compat_test.db"
    store = Store(str(db_path))
    store.init()

    # Seed test domain
    domain = CanonDomain(
        name="MCP Test Brand",
        summary="A brand for MCP testing.",
        positioning="For developers who need reliable tools.",
        status=DomainStatus.ACTIVE,
    )
    store.upsert_house(domain)

    # Seed key entry
    entry = CanonEntry(
        canon_domain_id=domain.id,
        section_type=SectionType.BENEFIT,
        priority=2,
        content="Super reliable tooling",
        status=EntryStatus.APPROVED,
    )
    store.upsert_key_message(entry)

    # Patch server.get_store and grounding_tools Store
    import src.grounding.tools as gt_module
    old_server_store = server_module.get_store
    old_gt_store = gt_module._get_store
    server_module.get_store = lambda: store
    gt_module._get_store = lambda: store

    yield store, domain, entry

    server_module.get_store = old_server_store
    gt_module._get_store = old_gt_store


def test_mcp_tool_alias_list_canon_domains(mock_mcp_store):
    from src.server import list_canon_domains, list_message_houses
    store, domain, _ = mock_mcp_store

    # Test list_canon_domains
    res = list_canon_domains()
    assert "domains" in res
    assert any(d["id"] == str(domain.id) for d in res["domains"])

    # Test list_message_houses (deprecated alias)
    with pytest.warns(DeprecationWarning) as record:
        res_alias = list_message_houses()
    assert len(record) > 0
    assert "domains" in res_alias
    assert any(d["id"] == str(domain.id) for d in res_alias["domains"])


def test_mcp_tool_alias_get_canon_domain(mock_mcp_store):
    from src.server import get_canon_domain, get_message_house
    store, domain, _ = mock_mcp_store

    # Test get_canon_domain
    res = get_canon_domain(domain_id=str(domain.id))
    assert res["domain_id"] == str(domain.id)
    assert res["domain_name"] == domain.name

    # Test get_message_house (deprecated alias)
    with pytest.warns(DeprecationWarning) as record:
        res_alias = get_message_house(house_id=str(domain.id))
    assert len(record) > 0
    assert res_alias["domain_id"] == str(domain.id)
    assert res_alias["domain_name"] == domain.name


def test_mcp_tool_alias_search_canon(mock_mcp_store):
    from src.server import search_canon, search_messaging
    store, domain, _ = mock_mcp_store

    # Test search_canon
    with patch("src.grounding.search.GroundingEngine.search") as mock_search:
        # mock search result
        mock_result = MagicMock()
        mock_result.results = []
        mock_result.grounding_context = MagicMock()
        mock_result.grounding_context.active_canon_domain_id = domain.id
        mock_result.grounding_context.canon_domain_name = domain.name
        mock_result.grounding_context.canon_domain_summary = domain.summary
        mock_result.model_dump.return_value = {
            "results": [{"message_house_id": domain.id, "key_message_id": uuid4(), "content": "Reliable", "score": 0.9, "section_type": "benefit"}]
        }
        mock_search.return_value = mock_result

        res = search_canon(query="reliability", canon_domains=[str(domain.id)])
        assert "results" in res
        assert res["results"][0]["canon_domain_id"] == domain.id

        # Test search_messaging (deprecated alias)
        with pytest.warns(DeprecationWarning) as record:
            res_alias = search_messaging(query="reliability", message_houses=[str(domain.id)])
        assert len(record) > 0
        assert "results" in res_alias
        assert res_alias["results"][0]["canon_domain_id"] == domain.id


def test_mcp_tool_alias_active_domain(mock_mcp_store):
    from src.server import set_active_domain, set_active_house
    store, domain, _ = mock_mcp_store

    # Test set_active_domain
    res = set_active_domain(domain_id=str(domain.id))
    assert "domain_id" in res
    assert res["domain_id"] == str(domain.id)

    # Test set_active_house (deprecated alias)
    with pytest.warns(DeprecationWarning) as record:
        res_alias = set_active_house(house_id=str(domain.id))
    assert len(record) > 0
    assert "domain_id" in res_alias
    assert res_alias["domain_id"] == str(domain.id)


def test_mcp_tool_alias_compare_domains(mock_mcp_store):
    from src.server import compare_canon_domains, compare_houses
    store, domain, _ = mock_mcp_store

    # Test compare_canon_domains
    res = compare_canon_domains(domain_ids=[str(domain.id)])
    assert isinstance(res, dict)

    # Test compare_houses (deprecated alias)
    with pytest.warns(DeprecationWarning) as record:
        res_alias = compare_houses(house_ids=[str(domain.id)])
    assert len(record) > 0
    assert isinstance(res_alias, dict)


def test_mcp_tool_alias_check_completeness(mock_mcp_store):
    from src.server import check_canon_completeness, check_framework_completeness
    store, domain, _ = mock_mcp_store

    # Test check_canon_completeness
    res = check_canon_completeness(domain_id=str(domain.id))
    assert "domain_name" in res
    assert res["domain_name"] == domain.name

    # Test check_framework_completeness (deprecated alias)
    with pytest.warns(DeprecationWarning) as record:
        res_alias = check_framework_completeness(house_id=str(domain.id))
    assert len(record) > 0
    assert "domain_name" in res_alias
    assert res_alias["domain_name"] == domain.name


def test_mcp_tool_alias_score_alignment(mock_mcp_store):
    from src.server import score_canon_alignment, score_alignment
    store, domain, _ = mock_mcp_store

    with patch("src.pipeline.alignment.AlignmentEngine.score") as mock_score:
        mock_report = MagicMock()
        mock_report.model_dump.return_value = {"overall_score": 85, "house_id": domain.id}
        mock_score.return_value = mock_report

        # Test score_canon_alignment
        res = score_canon_alignment(domain_id=str(domain.id), content="Test text")
        assert res["overall_score"] == 85
        assert res["domain_id"] == domain.id

        # Test score_alignment (deprecated alias)
        with pytest.warns(DeprecationWarning) as record:
            res_alias = score_alignment(house_id=str(domain.id), content="Test text")
        assert len(record) > 0
        assert res_alias["overall_score"] == 85
        assert res_alias["domain_id"] == domain.id


# ── Parameter Conflict & Validation Tests ─────────────────────────────────────

def test_grounding_type_conflicts_and_validation(test_setup):
    _, client, domain, _, _ = test_setup

    # 1. Conflicting parameters in POST (create) -> should raise 422
    resp_create_conflict = client.post("/api/canon-domains", json={
        "name": "Conflicting Brand",
        "document_type": "brand_guide",
        "grounding_type": "message_house"
    })
    assert resp_create_conflict.status_code == 422
    assert "Conflicting values" in resp_create_conflict.json()["detail"][0]["msg"]

    # 2. Conflicting parameters in PATCH (update) -> should raise 422
    resp_update_conflict = client.patch(f"/api/canon-domains/{domain.id}", json={
        "document_type": "brand_guide",
        "grounding_type": "message_house"
    })
    assert resp_update_conflict.status_code == 422
    assert "Conflicting values" in resp_update_conflict.json()["detail"][0]["msg"]

    # 3. Invalid grounding_type value -> should raise 422
    resp_invalid_gt = client.post("/api/canon-domains", json={
        "name": "Invalid Brand",
        "grounding_type": "invalid_grounding_type"
    })
    assert resp_invalid_gt.status_code == 422

    # 4. Valid separate document_type creation -> succeeds and returns brand_guide
    resp_doc_type = client.post("/api/canon-domains", json={
        "name": "Doc Type Brand",
        "document_type": "brand_guide"
    })
    assert resp_doc_type.status_code == 200
    new_id = resp_doc_type.json()["id"]

    resp_detail = client.get(f"/api/canon-domains/{new_id}")
    assert resp_detail.status_code == 200
    assert resp_detail.json()["document_type"] == "brand_guide"
    assert resp_detail.json()["grounding_type"] == "brand_guide"

    # 5. Valid separate grounding_type creation -> succeeds and returns competitive_brief
    resp_grounding_type = client.post("/api/canon-domains", json={
        "name": "Grounding Type Brand",
        "grounding_type": "competitive_brief"
    })
    assert resp_grounding_type.status_code == 200
    new_id_2 = resp_grounding_type.json()["id"]

    resp_detail_2 = client.get(f"/api/canon-domains/{new_id_2}")
    assert resp_detail_2.status_code == 200
    assert resp_detail_2.json()["document_type"] == "competitive_brief"
    assert resp_detail_2.json()["grounding_type"] == "competitive_brief"

