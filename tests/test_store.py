import pytest
import os
from uuid import uuid4, UUID

os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["PINECONE_API_KEY"] = "test-key"

from src.models import Channel, SpecStatus, Assertion, Spec, Audience, AssertionType
from src.store import Store


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "test.db"
    s = Store(str(db))
    s.init()
    return s


def test_upsert_and_get_spec(store):
    spec = Spec(
        name="Test Spec Q2 2026",
        source="manual",
        summary="Test positioning",
        positioning="Test value prop",
        tagline="Test tagline",
        differentiation="Test diff",
        status=SpecStatus.ACTIVE,
    )
    store.upsert_spec(spec)
    retrieved = store.get_spec(spec.id)
    assert retrieved is not None
    assert retrieved.name == "Test Spec Q2 2026"
    assert retrieved.positioning == "Test value prop"


def test_get_spec_by_name(store):
    spec = Spec(name="Acme Q2 2026", positioning="Position here")
    store.upsert_spec(spec)
    found = store.get_spec_by_name("Acme Q2 2026")
    assert found is not None
    assert found.id == spec.id
    not_found = store.get_spec_by_name("Nonexistent")
    assert not_found is None


def test_list_specs(store):
    spec1 = Spec(name="Spec A")
    spec2 = Spec(name="Spec B")
    store.upsert_spec(spec1)
    store.upsert_spec(spec2)
    specs = store.list_specs()
    assert len(specs) == 2


def test_key_messages(store):
    spec = Spec(name="Test Spec")
    store.upsert_spec(spec)

    msg = Assertion(
        spec_id=spec.id,
        assertion_type=AssertionType.CAPABILITY,
        priority=1,
        content="Test headline content",
        variants={"linkedin": "LinkedIn version"},
        audiences=["SMB CTO"],
        channels=[Channel.LINKEDIN],
    )
    store.upsert_key_message(msg)

    messages = store.get_key_messages(spec.id, include_unapproved=True)
    assert len(messages) == 1
    assert messages[0].content == "Test headline content"
    assert messages[0].assertion_type == AssertionType.CAPABILITY
    assert "linkedin" in messages[0].variants


def test_audiences(store):
    spec = Spec(name="Test Spec")
    store.upsert_spec(spec)

    audience = Audience(
        spec_id=spec.id,
        name="SMB CTO",
        description="Technical leader",
        qa_pairs=["Too complex"],
    )
    store.upsert_audience(audience)

    audiences = store.get_audiences(spec.id)
    assert len(audiences) == 1
    assert audiences[0].name == "SMB CTO"
    assert "Too complex" in audiences[0].qa_pairs


def test_delete_spec(store):
    spec = Spec(name="To Delete")
    store.upsert_spec(spec)
    assert store.get_spec(spec.id) is not None
    store.delete_spec(spec.id)
    assert store.get_spec(spec.id) is None


def test_upsert_updates_existing(store):
    spec = Spec(name="Original Name", positioning="Original")
    store.upsert_spec(spec)
    spec.name = "Updated Name"
    spec.positioning = "Updated"
    store.upsert_spec(spec)
    retrieved = store.get_spec(spec.id)
    assert retrieved.name == "Updated Name"
    assert retrieved.positioning == "Updated"


def test_search_filters_model():
    from src.models import SearchFilters
    f = SearchFilters(
        assertion_types=["headline", "benefit"],
        audiences=["SMB CTO"],
        channels=["linkedin"],
        min_priority=2,
    )
    assert "headline" in f.assertion_types
    assert f.min_priority == 2


def test_delete_key_message(store):
    spec = Spec(name="Test Spec")
    store.upsert_spec(spec)
    msg = Assertion(spec_id=spec.id, assertion_type=AssertionType.CAPABILITY, priority=1, content="Test msg")
    store.upsert_key_message(msg)
    assert len(store.get_key_messages(spec.id, include_unapproved=True)) == 1
    assert store.delete_key_message(msg.id) is True
    assert len(store.get_key_messages(spec.id, include_unapproved=True)) == 0


def test_delete_audience(store):
    spec = Spec(name="Test Spec")
    store.upsert_spec(spec)
    audience = Audience(spec_id=spec.id, name="Test Audience")
    store.upsert_audience(audience)
    assert len(store.get_audiences(spec.id)) == 1
    assert store.delete_audience(audience.id) is True
    assert len(store.get_audiences(spec.id)) == 0


def test_snapshots(store):
    spec = Spec(name="Snap Spec", positioning="Position A")
    store.upsert_spec(spec)
    msg = Assertion(spec_id=spec.id, assertion_type=AssertionType.CAPABILITY, priority=1, content="Test headline")
    store.upsert_key_message(msg)

    snap = store.create_snapshot(spec.id, label="Before edit")
    assert snap["id"]
    assert snap["label"] == "Before edit"

    snaps = store.list_snapshots(spec.id)
    assert len(snaps) == 1
    assert snaps[0]["message_count"] == 1

    full = store.get_snapshot(UUID(snap["id"]))
    assert full["snapshot_json"]["spec"]["positioning"] == "Position A"
    assert len(full["snapshot_json"]["messages"]) == 1

    assert store.delete_snapshot(UUID(snap["id"])) is True
    assert store.list_snapshots(spec.id) == []


def test_artifact_history(store):
    spec = Spec(name="Art Spec")
    store.upsert_spec(spec)

    record = store.save_artifact(
        spec_id=spec.id,
        skill_id="one_pager",
        spec_name=spec.name,
        sections={"positioning": "Test positioning", "tagline": "Test tagline"},
        raw_content="Full raw output here",
    )
    assert record["id"]
    assert record["skill_id"] == "one_pager"

    arts = store.list_artifacts(spec.id)
    assert len(arts) == 1
    assert arts[0]["section_count"] == 2

    full = store.get_artifact(UUID(record["id"]))
    assert full["sections"]["tagline"] == "Test tagline"
    assert full["raw_content"] == "Full raw output here"


def test_grounding_response_model():
    from src.models import GroundingContext, GroundingResult, GroundingResponse
    result = GroundingResult(
        chunk_id="c1",
        content="Test content",
        assertion_type="capability",
        priority=1,
        audience="SMB CTO",
        channel="all",
        confidence=0.95,
        rerank_reason="high score",
        source={"spec_id": str(uuid4()), "spec_name": "Test Spec"},
    )
    ctx = GroundingContext(
        active_spec_id=uuid4(),
        spec_name="Test Spec",
        confidence="high",
    )
    resp = GroundingResponse(results=[result], grounding_context=ctx)
    assert len(resp.results) == 1
    assert resp.grounding_context.confidence == "high"


def test_audience_governance_fields(store):
    from datetime import datetime, timezone
    spec = Spec(name="Gov Spec")
    store.upsert_spec(spec)

    audience = Audience(
        spec_id=spec.id,
        name="Gov Audience",
        status="in_review",
        approved_by="test-user",
        approved_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    store.upsert_audience(audience)

    audiences = store.get_audiences(spec.id)
    assert len(audiences) == 1
    assert audiences[0].status == "in_review"
    assert audiences[0].approved_by == "test-user"
    assert audiences[0].approved_at is not None