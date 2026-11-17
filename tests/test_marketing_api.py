"""REST surface (src/marketing/api.py) mounted on a bare FastAPI app, driven end to end."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.marketing.api import router
from src.marketing.store import MarketingStore, set_marketing_store


@pytest.fixture
def client(tmp_path):
    set_marketing_store(MarketingStore(f"sqlite:///{tmp_path / 'api.db'}").init())
    app = FastAPI()
    app.include_router(router)
    yield TestClient(app)
    set_marketing_store(None)


def test_full_flow_over_rest(client):
    r = client.post("/api/marketing/brands", json={
        "name": "Luna Pilates", "one_liner": "Pilates for desk workers.", "audience": "A tired analyst",
        "tone": ["calm"], "topics": ["posture", "breaks"], "cta": "Book a trial class.",
        "we_never_say": ["grind"], "weekly_quota": {"instagram": 3}})
    assert r.status_code == 200, r.text
    bid = r.json()["brand"]["id"]

    assert client.get("/api/marketing/brands").json()["count"] == 1
    assert client.get(f"/api/marketing/brands/{bid}").json()["canon"]["ready_for_generation"] is True

    r = client.patch(f"/api/marketing/brands/{bid}/canon", json={"locked_claims": ["Classes are 45 minutes."]})
    assert r.json()["canon"]["version"] == 2

    r = client.post(f"/api/marketing/brands/{bid}/check", json={"text": "Grind through 30 classes.", "channel": "instagram"})
    assert r.json()["ok"] is False and {"banned-phrase", "fabricated-number"} <= {v["rule"] for v in r.json()["hard"]}

    r = client.post(f"/api/marketing/brands/{bid}/generate",
                    json={"channel": "instagram", "start_date": "2026-11-16", "count": 2, "use_llm": False})
    assert r.status_code == 200 and r.json()["generated"] == 2
    cid1, cid2 = [i["id"] for i in r.json()["items"]]

    assert client.get(f"/api/marketing/brands/{bid}/queue").json()["count"] == 2

    r = client.post(f"/api/marketing/brands/{bid}/content/{cid1}/approve", json={"decided_by": "katia", "destination": "buffer"})
    assert r.json()["approved"] is True
    r = client.post(f"/api/marketing/brands/{bid}/content/{cid2}/reject", json={"reason": "too generic"})
    assert r.json()["rejected"] is True
    r = client.post(f"/api/marketing/brands/{bid}/content/{cid2}/reject", json={"reason": ""})
    assert r.status_code == 422 or r.status_code == 400  # pydantic min or tools ValueError

    r = client.post(f"/api/marketing/brands/{bid}/content/{cid1}/published", json={"external_ref": "ig:123"})
    assert r.json()["published"] is True
    res = client.get(f"/api/marketing/brands/{bid}/results").json()
    assert res["published_count"] == 1 and res["published"][0]["approved_by"] == "katia"


def test_errors_map_to_http_status(client):
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/api/marketing/brands/{missing}").status_code == 404
    assert client.get("/api/marketing/brands/not-a-uuid").status_code == 400
    r = client.post("/api/marketing/brands", json={"name": "X"})
    bid = r.json()["brand"]["id"]
    r = client.post(f"/api/marketing/brands/{bid}/generate", json={"use_llm": False})
    assert r.status_code == 200 and r.json()["blocked"] == "canon_not_ready"
    r = client.post(f"/api/marketing/brands/{bid}/content/{missing}/approve", json={})
    assert r.status_code == 404
