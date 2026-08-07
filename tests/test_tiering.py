import os
from uuid import UUID, uuid4
from unittest.mock import MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")

import pytest
from src.models import (
    Spec, Assertion, Spec, SectionType, AssertionStatus,
    ContentTier, SpecStatus, SearchFilters,
)
from src.store import Store


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "tiering_test.db"
    s = Store(str(db))
    s.init()
    return s


@pytest.fixture
def seeded_domain(store):
    domain = Spec(
        name="Tiering Test Domain",
        summary="A domain for content tiering tests.",
        positioning="Positioning for tiering tests.",
        status=SpecStatus.ACTIVE,
    )
    store.upsert_spec(domain)
    return domain


def _create_entry(store, domain, content, status=AssertionStatus.DRAFT, section_type=SectionType.HEADLINE, priority=1, content_tier=None):
    entry = Assertion(
        spec_id=domain.id,
        section_type=section_type,
        priority=priority,
        content=content,
        status=status,
        content_tier=content_tier,
    )
    store.upsert_assertion(entry)
    return entry


class TestContentTierEnum:
    """ContentTier enum values."""

    def test_enum_values(self):
        assert ContentTier.TIER_1_LOCKED.value == "tier_1_locked"
        assert ContentTier.TIER_2_STRUCTURED.value == "tier_2_structured"
        assert ContentTier.TIER_3_GROUNDED.value == "tier_3_grounded"


class TestContentTierOnEntry:
    """Content tier stored and retrieved on Assertion."""

    def test_create_entry_with_tier(self, store, seeded_domain):
        entry = _create_entry(store, seeded_domain, "T1 entry", content_tier=ContentTier.TIER_1_LOCKED)
        fetched = store.get_assertion(entry.id)
        assert fetched is not None
        assert fetched.content_tier == "tier_1_locked"

    def test_create_entry_without_tier(self, store, seeded_domain):
        entry = _create_entry(store, seeded_domain, "No tier entry", content_tier=None)
        fetched = store.get_assertion(entry.id)
        assert fetched is not None
        assert fetched.content_tier is None

    def test_update_entry_tier(self, store, seeded_domain):
        entry = _create_entry(store, seeded_domain, "Upgradeable", content_tier=ContentTier.TIER_3_GROUNDED)
        store.update_entry_tier(str(entry.id), "tier_1_locked")
        fetched = store.get_assertion(entry.id)
        assert fetched.content_tier == "tier_1_locked"

    def test_clear_entry_tier(self, store, seeded_domain):
        entry = _create_entry(store, seeded_domain, "Clearable", content_tier=ContentTier.TIER_2_STRUCTURED)
        store.update_entry_tier(str(entry.id), None)
        fetched = store.get_assertion(entry.id)
        assert fetched.content_tier is None

    def test_update_tier_nonexistent_entry(self, store):
        result = store.update_entry_tier(str(uuid4()), "tier_1_locked")
        assert result is None

    def test_invalid_tier_value_raises(self, store, seeded_domain):
        entry = _create_entry(store, seeded_domain, "Bad tier")
        with pytest.raises(ValueError):
            store.update_entry_tier(str(entry.id), "tier_4_fake")


class TestPromotionGate:
    """Entry must have content_tier before approving or locking."""

    def test_approve_without_tier_raises(self, store, seeded_domain):
        entry = _create_entry(store, seeded_domain, "No tier", content_tier=None)
        with pytest.raises(ValueError, match="Content tier must be assigned"):
            store.update_entry_status(str(entry.id), "approved")

    def test_lock_without_tier_raises(self, store, seeded_domain):
        entry = _create_entry(store, seeded_domain, "No tier", content_tier=None)
        with pytest.raises(ValueError, match="Content tier must be assigned"):
            store.update_entry_status(str(entry.id), "locked")

    def test_approve_with_tier_succeeds(self, store, seeded_domain):
        entry = _create_entry(store, seeded_domain, "Has tier", content_tier=ContentTier.TIER_2_STRUCTURED)
        result = store.update_entry_status(str(entry.id), "approved", approved_by="tester")
        assert result is not None
        assert result["status"] == "approved"

    def test_lock_with_tier_succeeds(self, store, seeded_domain):
        entry = _create_entry(store, seeded_domain, "Has tier", content_tier=ContentTier.TIER_1_LOCKED)
        result = store.update_entry_status(str(entry.id), "locked")
        assert result is not None
        assert result["status"] == "locked"

    def test_draft_and_in_review_allow_no_tier(self, store, seeded_domain):
        entry = _create_entry(store, seeded_domain, "No tier ok for draft")
        result = store.update_entry_status(str(entry.id), "in_review")
        assert result is not None
        assert result["status"] == "in_review"


class TestTierOnRetrievedEntries:
    """get_assertions includes content_tier."""

    def test_entries_include_tier(self, store, seeded_domain):
        _create_entry(store, seeded_domain, "T1", content_tier=ContentTier.TIER_1_LOCKED, status=AssertionStatus.APPROVED)
        _create_entry(store, seeded_domain, "T2", content_tier=ContentTier.TIER_2_STRUCTURED, status=AssertionStatus.APPROVED)
        _create_entry(store, seeded_domain, "No tier", status=AssertionStatus.APPROVED)
        entries = store.get_assertions(seeded_domain.id)
        assert len(entries) == 3
        tiers = {e.content_tier for e in entries}
        assert "tier_1_locked" in tiers
        assert "tier_2_structured" in tiers
        assert None in tiers


class TestGeneratorTierGrounding:
    """Tier affects ordering and annotation ONLY — never inclusion.

    Regression test for the production bug where legacy NULL-tier entries
    were silently dropped from artifact generation.
    """

    def _build(self, store, seeded_domain):
        from src.pipeline.generator import ArtifactGenerator
        with patch("src.pipeline.generator.OpenAI"):
            gen = ArtifactGenerator(store, "test-key")
        return gen._build_context(seeded_domain, store.get_assertions(seeded_domain.id), [], {})

    def test_untierd_entries_are_included(self, store, seeded_domain):
        """A domain whose entries ALL have NULL tier must still ground generation."""
        _create_entry(store, seeded_domain, "Legacy entry one", status=AssertionStatus.APPROVED)
        _create_entry(store, seeded_domain, "Legacy entry two", status=AssertionStatus.APPROVED)
        context = self._build(store, seeded_domain)
        assert "Legacy entry one" in context["assertions"]
        assert "Legacy entry two" in context["assertions"]

    def test_mixed_tiers_all_included(self, store, seeded_domain):
        _create_entry(store, seeded_domain, "T1 msg", content_tier=ContentTier.TIER_1_LOCKED, status=AssertionStatus.APPROVED)
        _create_entry(store, seeded_domain, "T2 msg", content_tier=ContentTier.TIER_2_STRUCTURED, status=AssertionStatus.APPROVED)
        _create_entry(store, seeded_domain, "No tier msg", status=AssertionStatus.APPROVED)
        context = self._build(store, seeded_domain)
        assert "T1 msg" in context["assertions"]
        assert "T2 msg" in context["assertions"]
        assert "No tier msg" in context["assertions"]

    def test_tier1_verbatim_directive_present(self, store, seeded_domain):
        _create_entry(store, seeded_domain, "Locked tagline text", content_tier=ContentTier.TIER_1_LOCKED, status=AssertionStatus.APPROVED)
        context = self._build(store, seeded_domain)
        km = context["assertions"]
        assert "TIER 1 — LOCKED" in km
        assert "VERBATIM" in km
        assert "Locked tagline text" in km

    def test_tier2_directive_present(self, store, seeded_domain):
        _create_entry(store, seeded_domain, "Structured claim", content_tier=ContentTier.TIER_2_STRUCTURED, status=AssertionStatus.APPROVED)
        context = self._build(store, seeded_domain)
        assert "TIER 2" in context["assertions"]

    def test_untierd_entries_carry_no_directive(self, store, seeded_domain):
        _create_entry(store, seeded_domain, "Plain legacy entry", status=AssertionStatus.APPROVED)
        context = self._build(store, seeded_domain)
        assert "TIER 1" not in context["assertions"]
        assert "TIER 2" not in context["assertions"]


class TestTier1VerbatimValidation:
    """Post-generation verbatim check for Tier 1 entries."""

    def _entry(self, content, tier=ContentTier.TIER_1_LOCKED):
        return Assertion(
            spec_id=uuid4(),
            section_type=SectionType.HEADLINE,
            priority=1,
            content=content,
            content_tier=tier,
        )

    def test_verbatim_use_passes(self):
        from src.pipeline.generator import find_tier1_violations
        entry = self._entry("Automate busywork and free strategic time.")
        output = "Our pitch: Automate busywork and free strategic time. That is the promise."
        assert find_tier1_violations([entry], output) == []

    def test_paraphrase_is_flagged(self):
        from src.pipeline.generator import find_tier1_violations
        entry = self._entry("Automate busywork and free strategic time for HR teams.")
        output = "We help HR teams automate their busywork so they gain strategic time back."
        violations = find_tier1_violations([entry], output)
        assert len(violations) == 1
        assert violations[0]["content"] == entry.content

    def test_unused_entry_not_flagged(self):
        from src.pipeline.generator import find_tier1_violations
        entry = self._entry("Completely unrelated locked claim about quantum widgets.")
        output = "This artifact talks about workflow efficiency and onboarding."
        assert find_tier1_violations([entry], output) == []

    def test_non_tier1_never_flagged(self):
        from src.pipeline.generator import find_tier1_violations
        entry = self._entry("Automate busywork and free strategic time.", tier=ContentTier.TIER_2_STRUCTURED)
        output = "We automate the busywork to free up your strategic time."
        assert find_tier1_violations([entry], output) == []

    def test_whitespace_differences_still_verbatim(self):
        from src.pipeline.generator import find_tier1_violations
        entry = self._entry("Automate busywork\nand free strategic time.")
        output = "Headline: Automate busywork and   free strategic time."
        assert find_tier1_violations([entry], output) == []


class TestTierMigration:
    """Additive migration creates content_tier column."""

    def test_migration_adds_column(self, tmp_path):
        db = tmp_path / "migrate_tier.db"
        s = Store(str(db))
        s.init()
        from sqlalchemy import inspect
        insp = inspect(s.engine)
        cols = {c["name"] for c in insp.get_columns("assertions")}
        assert "content_tier" in cols

    def test_migration_adds_vector_column(self, tmp_path):
        db = tmp_path / "migrate_vec_tier.db"
        s = Store(str(db))
        s.init()
        from sqlalchemy import inspect
        insp = inspect(s.engine)
        cols = {c["name"] for c in insp.get_columns("vector_metadata")}
        assert "content_tier" in cols
