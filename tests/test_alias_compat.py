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
    from src.models import Spec, Assertion, Persona, SectionType, AssertionStatus, SpecStatus

    db_path = tmp_path / "alias_compat_test.db"
    store = Store(str(db_path))
    store.init()

    # Seed one test domain
    domain = Spec(
        name="Compatibility Test Brand",
        summary="A brand for compatibility testing.",
        positioning="Positioning statement for compat testing.",
        tagline="Compat Tagline",
        differentiation="Differentiated product solution.",
        status=SpecStatus.ACTIVE,
    )
    store.upsert_spec(domain)

    # Seed one entry
    entry = Assertion(
        spec_id=domain.id,
        section_type=SectionType.BENEFIT,
        priority=1,
        content="Seed entry content",
        status=AssertionStatus.APPROVED,
        content_tier="tier_2_structured",
    )
    store.upsert_key_message(entry)

    # Seed one persona
    persona = Persona(
        spec_id=domain.id,
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

def test_specs_endpoint_aliases(test_setup):
    _, client, domain, _, _ = test_setup

    # Test GET list
    resp1 = client.get("/api/canon-domains")
    assert resp1.status_code == 200
    assert any(h["id"] == str(domain.id) for h in resp1.json())

    resp2 = client.get("/api/specs")
    assert resp2.status_code == 200
    assert any(h["id"] == str(domain.id) for h in resp2.json())

    # Test GET detail
    resp3 = client.get(f"/api/canon-domains/{domain.id}")
    assert resp3.status_code == 200
    assert resp3.json()["name"] == domain.name

    resp4 = client.get(f"/api/specs/{domain.id}")
    assert resp4.status_code == 200
    assert resp4.json()["name"] == domain.name


def test_assertions_endpoints_aliases(test_setup):
    _, client, domain, entry, _ = test_setup

    # Test POST create with spec graph parameter
    resp_create_spec = client.post("/api/entries", json={
        "spec_id": str(domain.id),
        "section_type": "headline",
        "content": "New headline content",
        "priority": 2
    })
    assert resp_create_spec.status_code == 200
    spec_id = resp_create_spec.json()["id"]

    # Test POST create with legacy parameter
    resp_create_legacy = client.post("/api/messages", json={
        "spec_id": str(domain.id),
        "section_type": "headline",
        "content": "Legacy parameter content",
        "priority": 3
    })
    assert resp_create_legacy.status_code == 200
    legacy_id = resp_create_legacy.json()["id"]

    # Test PATCH update
    resp_update_spec = client.patch(f"/api/entries/{spec_id}", json={"content": "Updated headline content"})
    assert resp_update_spec.status_code == 200

    resp_update_legacy = client.patch(f"/api/messages/{legacy_id}", json={"content": "Updated legacy content"})
    assert resp_update_legacy.status_code == 200

    # Set tiers before approving (promotion gate requires content_tier)
    resp_tier_spec = client.patch(f"/api/entries/{spec_id}/tier", json={"content_tier": "tier_2_structured"})
    assert resp_tier_spec.status_code == 200
    resp_tier_legacy = client.patch(f"/api/messages/{legacy_id}/tier", json={"content_tier": "tier_3_grounded"})
    assert resp_tier_legacy.status_code == 200

    # Test PATCH status
    resp_status_spec = client.patch(f"/api/entries/{spec_id}/status", json={"status": "approved", "approved_by": "tester"})
    assert resp_status_spec.status_code == 200
    assert resp_status_spec.json()["status"] in ("approved", "AssertionStatus.APPROVED")

    resp_status_legacy = client.patch(f"/api/messages/{legacy_id}/status", json={"status": "approved", "approved_by": "tester"})
    assert resp_status_legacy.status_code == 200

    # Test DELETE
    resp_del_spec = client.delete(f"/api/entries/{spec_id}")
    assert resp_del_spec.status_code == 200

    resp_del_legacy = client.delete(f"/api/messages/{legacy_id}")
    assert resp_del_legacy.status_code == 200


def test_spec_sub_endpoints_aliases(test_setup):
    store, client, domain, entry, _ = test_setup

    # review / review-trail / staleness / snapshots / artifacts / heatmap / coverage / usage-stats
    for path in ["review", "staleness", "review-trail", "snapshots", "artifacts", "heatmap", "coverage", "usage-stats", "mark-reviewed", "review-log"]:
        # Test spec path
        if path == "review":
            resp = client.post(f"/api/canon-domains/{domain.id}/review?performed_by=test")
        elif path == "snapshots":
            resp = client.get(f"/api/canon-domains/{domain.id}/snapshots")
        elif path == "mark-reviewed":
            resp = client.post(f"/api/canon-domains/{domain.id}/mark-reviewed")
        else:
            resp = client.get(f"/api/canon-domains/{domain.id}/{path}")
        assert resp.status_code in (200, 201), f"Spec path failed for /{path}: {resp.content}"

        # Test legacy spec path
        if path == "review":
            resp_leg = client.post(f"/api/specs/{domain.id}/review?performed_by=test")
        elif path == "snapshots":
            resp_leg = client.get(f"/api/specs/{domain.id}/snapshots")
        elif path == "mark-reviewed":
            resp_leg = client.post(f"/api/specs/{domain.id}/mark-reviewed")
        else:
            resp_leg = client.get(f"/api/specs/{domain.id}/{path}")
        assert resp_leg.status_code in (200, 201), f"Legacy path failed for /{path}: {resp_leg.content}"


# ── MCP Tool Alias Tests ──────────────────────────────────────────────────────

@pytest.fixture
def mock_mcp_store(tmp_path):
    """Setup a store and patch server-level functions."""
    from src.store import Store
    from src.models import Spec, Assertion, SectionType, SpecStatus, AssertionStatus
    import src.server as server_module

    db_path = tmp_path / "mcp_compat_test.db"
    store = Store(str(db_path))
    store.init()

    # Seed test domain
    domain = Spec(
        name="MCP Test Brand",
        summary="A brand for MCP testing.",
        positioning="For developers who need reliable tools.",
        status=SpecStatus.ACTIVE,
    )
    store.upsert_spec(domain)

    # Seed key entry
    entry = Assertion(
        spec_id=domain.id,
        section_type=SectionType.BENEFIT,
        priority=2,
        content="Super reliable tooling",
        status=AssertionStatus.APPROVED,
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

