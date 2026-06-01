import os
import hashlib
from uuid import UUID, uuid4
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

# Ensure key env vars are set
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")

from src.models import CanonDomain, GroundingType, DEPARTMENT_PRIMARY_GROUNDING
from src.auth import AuthContext
from src.store import Store

def test_department_mappings():
    """Verify department primary grounding mappings."""
    assert DEPARTMENT_PRIMARY_GROUNDING["Product Marketing"] == GroundingType.MESSAGE_HOUSE
    assert DEPARTMENT_PRIMARY_GROUNDING["Company Marketing"] == GroundingType.CORP_NARRATIVE
    assert DEPARTMENT_PRIMARY_GROUNDING["Enablement"] == GroundingType.PERSONA_LIBRARY
    assert DEPARTMENT_PRIMARY_GROUNDING["Product Management"] == GroundingType.COMPETITIVE_BRIEF

def test_domain_model_default_dept():
    """Verify department default is 'General' on models."""
    d = CanonDomain(name="Test Domain")
    assert d.department == "General"

def test_auth_context_scoping():
    """Verify AuthContext parses 'dept:<name>' scope and checks permissions correctly."""
    # Scoped user
    ctx_scoped = AuthContext(
        key_id="key-1",
        workspace_id="ws-1",
        scopes={"write", "dept:Product Marketing"},
        name="sme-pmark",
        is_admin=False,
        allowed_departments=["Product Marketing"],
    )
    assert ctx_scoped.has_department_access("Product Marketing") is True
    assert ctx_scoped.has_department_access("Company Marketing") is False
    assert ctx_scoped.has_department_access("General") is False

    # Admin user
    ctx_admin = AuthContext(
        key_id="key-2",
        workspace_id="ws-1",
        scopes={"admin", "write"},
        name="admin",
        is_admin=True,
        allowed_departments=[],
    )
    assert ctx_admin.has_department_access("Product Marketing") is True
    assert ctx_admin.has_department_access("Company Marketing") is True

    # General API key (no dept filters, allowed all)
    ctx_general = AuthContext(
        key_id="key-3",
        workspace_id="ws-1",
        scopes={"write"},
        name="general-user",
        is_admin=False,
        allowed_departments=[],
    )
    assert ctx_general.has_department_access("Product Marketing") is True
    assert ctx_general.has_department_access("Company Marketing") is True


@pytest.fixture
def store_and_client(tmp_path):
    """Setup a temporary database and FastAPI test client."""
    import src.web_app as web_app_module
    
    db_path = tmp_path / "dept_test.db"
    store = Store(str(db_path))
    store.init()

    # Seed test domains
    d1 = CanonDomain(
        name="PMM House",
        status="active",
        department="Product Marketing",
    )
    d2 = CanonDomain(
        name="Corp Narrative House",
        status="active",
        department="Company Marketing",
    )
    store.upsert_house(d1)
    store.upsert_house(d2)

    # Patch the web app's store
    import src.store as store_module
    old_store = web_app_module.store
    web_app_module.store = store
    old_store_instance = store_module._store_instance
    store_module._store_instance = store

    # Set auth to enabled for tests that need it
    old_auth_enabled = web_app_module.settings.auth_enabled
    web_app_module.settings.auth_enabled = True

    client = TestClient(web_app_module.app)

    yield store, client, d1, d2

    web_app_module.store = old_store
    store_module._store_instance = old_store_instance
    web_app_module.settings.auth_enabled = old_auth_enabled


def test_api_read_filtering(store_and_client):
    """Verify that department scoping filters domain list based on API key permissions."""
    store, client, d1, d2 = store_and_client

    # Define fake API key database records
    pmm_key = {
        "id": "pmm-key-id",
        "workspace_id": "default",
        "scopes": ["write", "dept:Product Marketing"],
        "name": "PMM SME",
        "is_active": True,
    }
    gen_key = {
        "id": "gen-key-id",
        "workspace_id": "default",
        "scopes": ["write"],
        "name": "General Writer",
        "is_active": True,
    }

    pmm_hash = hashlib.sha256(b"pmm-secret").hexdigest()
    gen_hash = hashlib.sha256(b"gen-secret").hexdigest()

    def mock_get_api_key_by_hash(key_hash):
        if key_hash == pmm_hash:
            return pmm_key
        if key_hash == gen_hash:
            return gen_key
        return None

    # Patch get_api_key_by_hash and touch_api_key in store to return our fake records
    with patch.object(store, "get_api_key_by_hash", side_effect=mock_get_api_key_by_hash), \
         patch.object(store, "touch_api_key"):
        
        # Test listing with PMM key
        resp = client.get("/api/canon-domains", headers={"X-API-Key": "pmm-secret"})
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["name"] == "PMM House"
        assert items[0]["department"] == "Product Marketing"

        # Test listing with general key
        resp = client.get("/api/canon-domains", headers={"X-API-Key": "gen-secret"})
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2


def test_api_write_guarding(store_and_client):
    """Verify that scoped keys are blocked from writing to other departments."""
    store, client, d1, d2 = store_and_client

    pmm_key = {
        "id": "pmm-key-id",
        "workspace_id": "default",
        "scopes": ["write", "dept:Product Marketing"],
        "name": "PMM SME",
        "is_active": True,
    }
    secret_hash = hashlib.sha256(b"secret").hexdigest()

    with patch.object(store, "get_api_key_by_hash", return_value=pmm_key), \
         patch.object(store, "touch_api_key"):

        # 1. Modify domain in own department -> Success
        resp = client.patch(f"/api/canon-domains/{d1.id}", json={"tagline": "PMM tag"}, headers={"X-API-Key": "secret"})
        assert resp.status_code == 200

        # 2. Modify domain in another department -> Forbidden 403
        resp2 = client.patch(f"/api/canon-domains/{d2.id}", json={"tagline": "Corp tag"}, headers={"X-API-Key": "secret"})
        assert resp2.status_code == 403

        # 3. Create domain in another department -> Forbidden 403
        resp3 = client.post("/api/canon-domains", json={
            "name": "Unauthorized Company Domain",
            "department": "Company Marketing"
        }, headers={"X-API-Key": "secret"})
        assert resp3.status_code == 403

        # 4. Create domain in own department -> Success
        resp4 = client.post("/api/canon-domains", json={
            "name": "Authorized PMM Domain",
            "department": "Product Marketing"
        }, headers={"X-API-Key": "secret"})
        assert resp4.status_code == 200


def test_mcp_list_departments(store_and_client):
    """Verify MCP list_departments tool returns grounding type and counts."""
    from src.server import list_departments, list_canon_domains
    import src.grounding.tools as gt_module
    store, client, d1, d2 = store_and_client

    with patch("src.server.get_store", return_value=store), \
         patch("src.grounding.tools._get_store", return_value=store):
        # Test list_departments
        depts_res = list_departments()
        assert "departments" in depts_res
        depts = depts_res["departments"]
        
        pmm_dept = next(d for d in depts if d["department"] == "Product Marketing")
        assert pmm_dept["domain_count"] == 1
        assert pmm_dept["primary_grounding_type"] == str(GroundingType.MESSAGE_HOUSE)

        corp_dept = next(d for d in depts if d["department"] == "Company Marketing")
        assert corp_dept["domain_count"] == 1
        assert corp_dept["primary_grounding_type"] == str(GroundingType.CORP_NARRATIVE)

        # Test list_canon_domains with department filter
        res_all = list_canon_domains()
        assert len(res_all["domains"]) == 2

        res_pmm = list_canon_domains(department="Product Marketing")
        assert len(res_pmm["domains"]) == 1
        assert res_pmm["domains"][0]["name"] == "PMM House"
