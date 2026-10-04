"""Audience Profiles: first-class tone/style/CTA constraints enforced at generation time."""

import os
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from src.models import AudienceProfile, CanonDomain, CanonEntry, DomainStatus, EntryStatus, GroundingType, SectionType


@pytest.fixture
def store(tmp_path):
    import src.store as store_mod
    from src.store import Store
    s = Store(str(tmp_path / "audience_profiles_test.db"))
    s.init()
    prev = store_mod._store_instance
    store_mod._store_instance = s
    yield s
    store_mod._store_instance = prev


def test_upsert_and_get_audience_profile(store):
    profile = AudienceProfile(name="LinkedIn Executives", tone_professionalism=0.9, tone_warmth=0.3,
                               reading_level="executive", banned_phrases=["synergy"], required_cta="Book a demo")
    store.upsert_audience_profile(profile)
    fetched = store.get_audience_profile(profile.id)
    assert fetched.name == "LinkedIn Executives"
    assert fetched.tone_professionalism == 0.9
    assert fetched.banned_phrases == ["synergy"]
    assert fetched.required_cta == "Book a demo"


def test_list_audience_profiles_scoped_by_workspace(store):
    store.upsert_audience_profile(AudienceProfile(name="A", workspace_id="default"))
    store.upsert_audience_profile(AudienceProfile(name="B", workspace_id="other"))
    assert [p.name for p in store.list_audience_profiles("default")] == ["A"]
    assert [p.name for p in store.list_audience_profiles("other")] == ["B"]


def test_delete_audience_profile(store):
    profile = AudienceProfile(name="Temp")
    store.upsert_audience_profile(profile)
    assert store.delete_audience_profile(profile.id) is True
    assert store.get_audience_profile(profile.id) is None
    assert store.delete_audience_profile(profile.id) is False


def _setup_domain(store):
    domain = CanonDomain(name="Acme", grounding_type=GroundingType.MESSAGE_HOUSE, status=DomainStatus.ACTIVE,
                          brand_personality="Bold")
    store.upsert_canon_domain(domain)
    entry = CanonEntry(canon_domain_id=domain.id, section_type=SectionType.PROOF_POINT, priority=1,
                        content="Trusted by 500 companies.", status=EntryStatus.APPROVED)
    store.upsert_canon_entry(entry)
    return domain


def _mock_llm(content):
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [MagicMock(message=MagicMock(content=content))]
    return client


def test_generate_applies_audience_profile_tone_and_strips_banned_phrase(store, tmp_path):
    from src.pipeline.generator import ArtifactGenerator
    from src.pipeline.skills import SkillManager

    domain = _setup_domain(store)
    profile = AudienceProfile(name="Formal Execs", tone_professionalism=1.0, tone_warmth=0.1,
                               reading_level="executive", banned_phrases=["game-changing"])
    store.upsert_audience_profile(profile)

    skills = SkillManager(str(tmp_path / "skills"))
    client = _mock_llm("positioning: This game-changing product is trusted by 500 companies.")
    with patch("src.config.llm_client", return_value=client):
        generator = ArtifactGenerator(store, skills, model="gpt-4o-mini")
        artifact = generator.generate("one_pager", str(domain.id), {"audience_profile_id": str(profile.id)})

    sent_prompt = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "Professionalism level: 1.0" in sent_prompt
    assert "Reading level: executive" in sent_prompt
    assert "game-changing" not in artifact.sections.get("positioning", "").lower()


def test_generate_flags_missing_required_cta_without_blocking(store, tmp_path, caplog):
    from src.pipeline.generator import ArtifactGenerator
    from src.pipeline.skills import SkillManager

    domain = _setup_domain(store)
    profile = AudienceProfile(name="CTA Required", required_cta="Book a demo today")
    store.upsert_audience_profile(profile)

    skills = SkillManager(str(tmp_path / "skills"))
    client = _mock_llm("positioning: No call to action here.")

    import logging
    with caplog.at_level(logging.WARNING), patch("src.config.llm_client", return_value=client):
        generator = ArtifactGenerator(store, skills, model="gpt-4o-mini")
        artifact = generator.generate("one_pager", str(domain.id), {"audience_profile_id": str(profile.id)})

    assert artifact is not None  # never blocks generation
    assert any("required a CTA" in r.message for r in caplog.records)


def test_explicit_tone_sliders_override_profile_defaults(store, tmp_path):
    from src.pipeline.generator import ArtifactGenerator
    from src.pipeline.skills import SkillManager

    domain = _setup_domain(store)
    profile = AudienceProfile(name="Casual", tone_professionalism=0.1)
    store.upsert_audience_profile(profile)

    skills = SkillManager(str(tmp_path / "skills"))
    client = _mock_llm("positioning: Hi.")
    with patch("src.config.llm_client", return_value=client):
        generator = ArtifactGenerator(store, skills, model="gpt-4o-mini")
        generator.generate("one_pager", str(domain.id), {"audience_profile_id": str(profile.id), "tone_professionalism": 0.95})

    sent_prompt = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "Professionalism level: 0.95" in sent_prompt


# ── API endpoint wiring ──────────────────────────────────────────────────────

def test_audience_profile_crud_api(tmp_path):
    import src.web_app as web_app_module
    from src.store import Store
    from fastapi.testclient import TestClient

    test_store = Store(str(tmp_path / "audience_profiles_api_test.db"))
    test_store.init()
    old_store = web_app_module.store
    web_app_module.store = test_store
    client = TestClient(web_app_module.app)
    try:
        resp = client.post("/api/audience-profiles", json={"name": "Devs", "tone_professionalism": 0.4})
        assert resp.status_code == 201, resp.text
        profile_id = resp.json()["id"]

        resp2 = client.get("/api/audience-profiles")
        assert resp2.status_code == 200
        assert len(resp2.json()) == 1

        resp3 = client.put(f"/api/audience-profiles/{profile_id}", json={"name": "Devs", "tone_professionalism": 0.8})
        assert resp3.status_code == 200
        assert resp3.json()["tone_professionalism"] == 0.8

        resp4 = client.delete(f"/api/audience-profiles/{profile_id}")
        assert resp4.status_code == 200
        assert client.get("/api/audience-profiles").json() == []
    finally:
        web_app_module.store = old_store
