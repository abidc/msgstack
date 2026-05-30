import pytest
import os
from uuid import uuid4, UUID

os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["PINECONE_API_KEY"] = "test-key"

from src.models import Channel, HouseStatus, KeyMessage, MessageHouse, Persona, SectionType
from src.store import Store


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "test.db"
    s = Store(str(db))
    s.init()
    return s


def test_upsert_and_get_house(store):
    house = MessageHouse(
        name="Test House Q2 2026",
        source="manual",
        summary="Test positioning",
        positioning="Test value prop",
        tagline="Test tagline",
        differentiation="Test diff",
        status=HouseStatus.ACTIVE,
    )
    store.upsert_house(house)
    retrieved = store.get_house(house.id)
    assert retrieved is not None
    assert retrieved.name == "Test House Q2 2026"
    assert retrieved.positioning == "Test value prop"


def test_get_house_by_name(store):
    house = MessageHouse(name="Acme Q2 2026", positioning="Position here")
    store.upsert_house(house)
    found = store.get_house_by_name("Acme Q2 2026")
    assert found is not None
    assert found.id == house.id
    not_found = store.get_house_by_name("Nonexistent")
    assert not_found is None


def test_list_houses(store):
    house1 = MessageHouse(name="House A")
    house2 = MessageHouse(name="House B")
    store.upsert_house(house1)
    store.upsert_house(house2)
    houses = store.list_houses()
    assert len(houses) == 2


def test_key_messages(store):
    house = MessageHouse(name="Test House")
    store.upsert_house(house)

    msg = KeyMessage(
        message_house_id=house.id,
        section_type=SectionType.HEADLINE,
        priority=1,
        content="Test headline content",
        variants={"linkedin": "LinkedIn version"},
        personas=["SMB CTO"],
        channels=[Channel.LINKEDIN],
    )
    store.upsert_key_message(msg)

    messages = store.get_key_messages(house.id)
    assert len(messages) == 1
    assert messages[0].content == "Test headline content"
    assert messages[0].section_type == SectionType.HEADLINE
    assert "linkedin" in messages[0].variants


def test_personas(store):
    house = MessageHouse(name="Test House")
    store.upsert_house(house)

    persona = Persona(
        message_house_id=house.id,
        name="SMB CTO",
        description="Technical leader",
        pain_points=["Cost", "Complexity"],
        buying_triggers=["CFO pressure"],
        objections=["Too complex"],
    )
    store.upsert_persona(persona)

    personas = store.get_personas(house.id)
    assert len(personas) == 1
    assert personas[0].name == "SMB CTO"
    assert "Cost" in personas[0].pain_points


def test_delete_house(store):
    house = MessageHouse(name="To Delete")
    store.upsert_house(house)
    assert store.get_house(house.id) is not None
    store.delete_house(house.id)
    assert store.get_house(house.id) is None


def test_upsert_updates_existing(store):
    house = MessageHouse(name="Original Name", positioning="Original")
    store.upsert_house(house)
    house.name = "Updated Name"
    house.positioning = "Updated"
    store.upsert_house(house)
    retrieved = store.get_house(house.id)
    assert retrieved.name == "Updated Name"
    assert retrieved.positioning == "Updated"


def test_search_filters_model():
    from src.models import SearchFilters
    f = SearchFilters(
        section_types=["headline", "benefit"],
        personas=["SMB CTO"],
        channels=["linkedin"],
        min_priority=2,
    )
    assert "headline" in f.section_types
    assert f.min_priority == 2


def test_delete_key_message(store):
    house = MessageHouse(name="Test House")
    store.upsert_house(house)
    msg = KeyMessage(message_house_id=house.id, section_type=SectionType.BENEFIT, priority=1, content="Test msg")
    store.upsert_key_message(msg)
    assert len(store.get_key_messages(house.id)) == 1
    assert store.delete_key_message(msg.id) is True
    assert len(store.get_key_messages(house.id)) == 0


def test_delete_persona(store):
    house = MessageHouse(name="Test House")
    store.upsert_house(house)
    persona = Persona(message_house_id=house.id, name="Test Persona")
    store.upsert_persona(persona)
    assert len(store.get_personas(house.id)) == 1
    assert store.delete_persona(persona.id) is True
    assert len(store.get_personas(house.id)) == 0


def test_snapshots(store):
    house = MessageHouse(name="Snap House", positioning="Position A")
    store.upsert_house(house)
    msg = KeyMessage(message_house_id=house.id, section_type=SectionType.HEADLINE, priority=1, content="Test headline")
    store.upsert_key_message(msg)

    snap = store.create_snapshot(house.id, label="Before edit")
    assert snap["id"]
    assert snap["label"] == "Before edit"

    snaps = store.list_snapshots(house.id)
    assert len(snaps) == 1
    assert snaps[0]["message_count"] == 1

    full = store.get_snapshot(UUID(snap["id"]))
    assert full["snapshot_json"]["house"]["positioning"] == "Position A"
    assert len(full["snapshot_json"]["messages"]) == 1

    assert store.delete_snapshot(UUID(snap["id"])) is True
    assert store.list_snapshots(house.id) == []


def test_artifact_history(store):
    house = MessageHouse(name="Art House")
    store.upsert_house(house)

    record = store.save_artifact(
        house_id=house.id,
        skill_id="one_pager",
        house_name=house.name,
        sections={"positioning": "Test positioning", "tagline": "Test tagline"},
        raw_content="Full raw output here",
    )
    assert record["id"]
    assert record["skill_id"] == "one_pager"

    arts = store.list_artifacts(house.id)
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
        section_type="headline",
        priority=1,
        persona="SMB CTO",
        channel="all",
        confidence=0.95,
        rerank_reason="high score",
        source={"house_id": str(uuid4()), "house_name": "Test House"},
    )
    ctx = GroundingContext(
        active_house_id=uuid4(),
        house_name="Test House",
        confidence="high",
    )
    resp = GroundingResponse(results=[result], grounding_context=ctx)
    assert len(resp.results) == 1
    assert resp.grounding_context.confidence == "high"


def test_persona_governance_fields(store):
    from datetime import datetime, timezone
    house = MessageHouse(name="Gov House")
    store.upsert_house(house)

    persona = Persona(
        message_house_id=house.id,
        name="Gov Persona",
        status="in_review",
        approved_by="test-user",
        approved_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    store.upsert_persona(persona)

    personas = store.get_personas(house.id)
    assert len(personas) == 1
    assert personas[0].status == "in_review"
    assert personas[0].approved_by == "test-user"
    assert personas[0].approved_at is not None