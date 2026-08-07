import os
from uuid import UUID, uuid4
from unittest.mock import MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")

import pytest
from src.models import Spec, Assertion, SectionType, AssertionStatus, SpecStatus, SearchFilters
from src.store import Store


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "approval_test.db"
    s = Store(str(db))
    s.init()
    return s


@pytest.fixture
def seeded_domain(store):
    domain = Spec(
        name="Approval Test Domain",
        summary="A domain for approval gating tests.",
        positioning="Positioning for approval tests.",
        status=SpecStatus.ACTIVE,
    )
    store.upsert_spec(domain)
    return domain


def _create_entry(store, domain, content, status, section_type=SectionType.HEADLINE, priority=1):
    entry = Assertion(
        spec_id=domain.id,
        section_type=section_type,
        priority=priority,
        content=content,
        status=status,
    )
    store.upsert_assertion(entry)
    return entry


class TestGetAssertions:
    """Tests for store.get_assertions approval gating."""

    def test_default_hides_draft_entries(self, store, seeded_domain):
        _create_entry(store, seeded_domain, "Approved msg", AssertionStatus.APPROVED)
        _create_entry(store, seeded_domain, "Draft msg", AssertionStatus.DRAFT)

        entries = store.get_assertions(seeded_domain.id)
        assert len(entries) == 1
        assert entries[0].content == "Approved msg"

    def test_include_unapproved_shows_draft(self, store, seeded_domain):
        _create_entry(store, seeded_domain, "Approved msg", AssertionStatus.APPROVED)
        _create_entry(store, seeded_domain, "Draft msg", AssertionStatus.DRAFT)

        entries = store.get_assertions(seeded_domain.id, include_unapproved=True)
        assert len(entries) == 2

    def test_locked_entries_always_appear(self, store, seeded_domain):
        _create_entry(store, seeded_domain, "Locked msg", AssertionStatus.LOCKED)
        _create_entry(store, seeded_domain, "Draft msg", AssertionStatus.DRAFT)

        entries = store.get_assertions(seeded_domain.id)
        assert len(entries) == 1
        assert entries[0].content == "Locked msg"

    def test_outdated_entries_hidden_by_default(self, store, seeded_domain):
        _create_entry(store, seeded_domain, "Approved msg", AssertionStatus.APPROVED)
        _create_entry(store, seeded_domain, "Outdated msg", AssertionStatus.OUTDATED)

        entries = store.get_assertions(seeded_domain.id)
        assert len(entries) == 1
        assert entries[0].content == "Approved msg"

    def test_in_review_hidden_by_default(self, store, seeded_domain):
        _create_entry(store, seeded_domain, "Approved msg", AssertionStatus.APPROVED)
        _create_entry(store, seeded_domain, "In review msg", AssertionStatus.IN_REVIEW)

        entries = store.get_assertions(seeded_domain.id)
        assert len(entries) == 1
        assert entries[0].content == "Approved msg"

    def test_include_unapproved_shows_in_review(self, store, seeded_domain):
        _create_entry(store, seeded_domain, "Approved msg", AssertionStatus.APPROVED)
        _create_entry(store, seeded_domain, "In review msg", AssertionStatus.IN_REVIEW)

        entries = store.get_assertions(seeded_domain.id, include_unapproved=True)
        assert len(entries) == 2


class TestGetKeyMessagesAlias:
    """Deprecated alias must also respect approval gating."""

    def test_alias_default_hides_draft(self, store, seeded_domain):
        _create_entry(store, seeded_domain, "Approved msg", AssertionStatus.APPROVED)
        _create_entry(store, seeded_domain, "Draft msg", AssertionStatus.DRAFT)

        entries = store.get_key_messages(seeded_domain.id)
        assert len(entries) == 1

    def test_alias_include_unapproved(self, store, seeded_domain):
        _create_entry(store, seeded_domain, "Draft msg", AssertionStatus.DRAFT)
        entries = store.get_key_messages(seeded_domain.id, include_unapproved=True)
        assert len(entries) == 1


class TestGetAssertion:
    """get_assertion (single by ID) should work regardless of status."""

    def test_get_single_entry_by_id(self, store, seeded_domain):
        entry = _create_entry(store, seeded_domain, "Draft msg", AssertionStatus.DRAFT)
        fetched = store.get_assertion(entry.id)
        assert fetched is not None
        assert fetched.content == "Draft msg"

    def test_get_single_locked_entry(self, store, seeded_domain):
        entry = _create_entry(store, seeded_domain, "Locked msg", AssertionStatus.LOCKED)
        fetched = store.get_assertion(entry.id)
        assert fetched is not None


class TestFallbackSearch:
    """_fallback_search in GroundingEngine must respect approval gating."""

    @pytest.fixture
    def engine_with_entries(self, tmp_path, store, seeded_domain):
        from src.grounding.search import GroundingEngine
        _create_entry(store, seeded_domain, "Approved headline", AssertionStatus.APPROVED)
        _create_entry(store, seeded_domain, "Draft headline", AssertionStatus.DRAFT, priority=2)
        _create_entry(store, seeded_domain, "Locked headline", AssertionStatus.LOCKED, priority=3)
        _create_entry(store, seeded_domain, "Outdated headline", AssertionStatus.OUTDATED, priority=4)

        with patch("src.grounding.search.OpenAI"):
            engine = GroundingEngine.__new__(GroundingEngine)
            engine.store = store
            engine.index = None
            engine.namespace = "default"
        return engine

    def test_fallback_default_excludes_draft_and_outdated(self, engine_with_entries, seeded_domain):
        engine = engine_with_entries
        filters = SearchFilters(specs=[str(seeded_domain.id)])
        resp = engine._fallback_search("headline", filters)
        contents = [r.content for r in resp.results]
        assert "Approved headline" in contents
        assert "Locked headline" in contents
        assert "Draft headline" not in contents
        assert "Outdated headline" not in contents

    def test_fallback_include_unapproved_shows_draft(self, engine_with_entries, seeded_domain):
        engine = engine_with_entries
        filters = SearchFilters(specs=[str(seeded_domain.id)], include_drafts=True)
        resp = engine._fallback_search("headline", filters)
        contents = [r.content for r in resp.results]
        assert "Draft headline" in contents
        assert "Outdated headline" not in contents


class TestRerank:
    """_rerank must respect approval gating."""

    @pytest.fixture
    def engine(self, tmp_path, store):
        from src.grounding.search import GroundingEngine
        with patch("src.grounding.search.OpenAI"):
            engine = GroundingEngine.__new__(GroundingEngine)
            engine.store = store
            engine.namespace = "default"
        return engine

    def test_rerank_excludes_outdated(self, engine):
        matches = [
            {"id": "a", "score": 0.9, "metadata": {"content": "approved msg", "assertion_id": str(uuid4())}},
            {"id": "b", "score": 0.8, "metadata": {"content": "outdated msg", "assertion_id": str(uuid4())}},
        ]
        key_message_ids = [m["metadata"]["assertion_id"] for m in matches]
        with patch("src.store.KeyMessageModel") as MockKm, patch.object(engine.store, "session"):
            with engine.store.session() as s:
                row_a = MagicMock()
                row_a.id = key_message_ids[0]
                row_a.status = "approved"
                row_b = MagicMock()
                row_b.id = key_message_ids[1]
                row_b.status = "outdated"
                s.query.return_value.filter.return_value.all.return_value = [row_a, row_b]

                reranked = engine._rerank("test", matches, top_k=5, filters=SearchFilters())
                assert len(reranked) == 1
                assert reranked[0]["id"] == "a"


class TestGetEntryHistory:
    """Tests for get_assertion_history MCP tool."""

    def test_get_entry_history_returns_trail(self, mcp_test_setup):
        store, domain, _ = mcp_test_setup
        from src.grounding.tools import get_assertion_history

        entry = _create_entry(store, domain, "Test msg", AssertionStatus.DRAFT)
        store.update_entry_tier(str(entry.id), "tier_2_structured")
        store.update_entry_status(str(entry.id), "in_review", approved_by="reviewer")
        store.update_entry_status(str(entry.id), "approved", approved_by="approver")

        result = get_assertion_history(str(entry.id))
        assert result["assertion_id"] == str(entry.id)
        assert result["current_status"] == "approved"
        assert result["count"] == 3
        actions = [t["action"] for t in result["trail"]]
        assert "approved" in actions
        assert "in_review" in actions
        assert "tier_update" in actions

    def test_get_entry_history_not_found(self, mcp_test_setup):
        from src.grounding.tools import get_assertion_history

        result = get_assertion_history(str(uuid4()))
        assert "error" in result

    def test_get_entry_history_invalid_id(self, mcp_test_setup):
        from src.grounding.tools import get_assertion_history

        result = get_assertion_history("not-a-uuid")
        assert "error" in result

    def test_get_entry_history_empty_for_new_entry(self, mcp_test_setup):
        store, domain, _ = mcp_test_setup
        from src.grounding.tools import get_assertion_history

        entry = _create_entry(store, domain, "Fresh msg", AssertionStatus.DRAFT)
        result = get_assertion_history(str(entry.id))
        assert result["assertion_id"] == str(entry.id)
        assert result["count"] == 0
        assert result["trail"] == []


class TestGetSpecApprovalGating:
    """Test that get_spec / get_spec respect approval gating."""

    def test_get_spec_default_hides_draft(self, mcp_test_setup):
        store, domain, entry = mcp_test_setup
        from src.grounding.tools import get_spec

        result = get_spec(spec_id=str(domain.id))
        assert "assertions" in result
        for m in result["assertions"]:
            assert m.get("status") in ("approved", "locked")

    def test_get_spec_include_unapproved_shows_draft(self, mcp_test_setup):
        store, domain, entry = mcp_test_setup
        from src.grounding.tools import get_spec

        # Add a draft entry
        draft = _create_entry(store, domain, "Draft msg", AssertionStatus.DRAFT)
        result = get_spec(spec_id=str(domain.id), include_unapproved=True)
        contents = [m["content"] for m in result["assertions"]]
        assert "Draft msg" in contents


@pytest.fixture
def mcp_test_setup(tmp_path):
    from src.store import Store
    from src.models import Spec, Assertion, SectionType, SpecStatus, AssertionStatus
    import src.server as server_module
    import src.grounding.tools as gt_module

    store = Store(str(tmp_path / "mcp_gating_test.db"))
    store.init()

    domain = Spec(
        name="MCP Gating Test",
        summary="Test",
        positioning="Positioning text.",
        status=SpecStatus.ACTIVE,
    )
    store.upsert_spec(domain)

    entry = Assertion(
        spec_id=domain.id,
        section_type=SectionType.BENEFIT,
        priority=1,
        content="Approved benefit",
        status=AssertionStatus.APPROVED,
        content_tier="tier_2_structured",
    )
    store.upsert_assertion(entry)

    old_server_store = server_module.get_store
    old_gt_store = gt_module._get_store
    server_module.get_store = lambda: store
    gt_module._get_store = lambda: store

    yield store, domain, entry

    server_module.get_store = old_server_store
    gt_module._get_store = old_gt_store
