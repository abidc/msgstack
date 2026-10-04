import pytest
from uuid import UUID, uuid4
import sqlite3
from datetime import datetime
from src.models import CanonDomain, CanonEntry, ContentTier, EntryStatus, DomainStatus
from src.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(f"sqlite:///{tmp_path / 'test_dri.db'}")
    s.init()

    house = CanonDomain(
        id=uuid4(),
        name="DRI Test House",
        grounding_type="message_house",
        dri="alice@example.com",
    )
    s.upsert_canon_domain(house)
    return s, house


def test_domain_dri_persisted(store):
    s, house = store
    fetched = s.get_canon_domain(house.id)
    assert fetched is not None
    assert fetched.dri == "alice@example.com"


def test_set_domain_dri(store):
    s, house = store
    result = s.set_domain_dri(str(house.id), "bob@example.com")
    assert result is not None
    assert result["dri"] == "bob@example.com"
    fetched = s.get_canon_domain(house.id)
    assert fetched.dri == "bob@example.com"


def test_set_domain_dri_nonexistent(store):
    s, _ = store
    result = s.set_domain_dri(str(uuid4()), "nobody@example.com")
    assert result is None


def test_entry_dri_defaults_empty(store):
    s, house = store
    entry = CanonEntry(
        id=uuid4(),
        canon_domain_id=house.id,
        section_type="brand_voice",
        content="Hello",
        priority=0,
    )
    s.upsert_canon_entry(entry)
    fetched = s.get_canon_entry(entry.id)
    assert fetched is not None
    assert fetched.dri == ""


def test_entry_dri_override(store):
    s, house = store
    entry = CanonEntry(
        id=uuid4(),
        canon_domain_id=house.id,
        section_type="brand_voice",
        content="Hello",
        priority=0,
        dri="override@example.com",
    )
    s.upsert_canon_entry(entry)
    fetched = s.get_canon_entry(entry.id)
    assert fetched.dri == "override@example.com"


def test_set_entry_dri(store):
    s, house = store
    entry = CanonEntry(
        id=uuid4(),
        canon_domain_id=house.id,
        section_type="brand_voice",
        content="Hello",
        priority=0,
    )
    s.upsert_canon_entry(entry)
    result = s.set_entry_dri(str(entry.id), "entry@example.com")
    assert result is not None
    assert result["dri"] == "entry@example.com"
    fetched = s.get_canon_entry(entry.id)
    assert fetched.dri == "entry@example.com"


def test_set_entry_dri_nonexistent(store):
    s, _ = store
    result = s.set_entry_dri(str(uuid4()), "nobody@example.com")
    assert result is None


def test_get_effective_dri_returns_entry_dri_when_set(store):
    s, house = store
    entry = CanonEntry(
        id=uuid4(),
        canon_domain_id=house.id,
        section_type="brand_voice",
        content="Hello",
        priority=0,
        dri="entry@example.com",
    )
    s.upsert_canon_entry(entry)
    eff = s.get_effective_dri(str(entry.id))
    assert eff == "entry@example.com"


def test_get_effective_dri_falls_back_to_domain(store):
    s, house = store
    entry = CanonEntry(
        id=uuid4(),
        canon_domain_id=house.id,
        section_type="brand_voice",
        content="Hello",
        priority=0,
    )
    s.upsert_canon_entry(entry)
    eff = s.get_effective_dri(str(entry.id))
    assert eff == "alice@example.com"


def test_get_effective_dri_nonexistent_entry(store):
    s, _ = store
    eff = s.get_effective_dri(str(uuid4()))
    assert eff == ""


def test_entry_dri_in_get_entries(store):
    s, house = store
    entry = CanonEntry(
        id=uuid4(),
        canon_domain_id=house.id,
        section_type="brand_voice",
        content="Hello",
        priority=0,
        dri="in-list@example.com",
        content_tier=ContentTier.TIER_2_STRUCTURED,
    )
    s.upsert_canon_entry(entry)
    s.update_entry_status(str(entry.id), "approved")
    entries = s.get_canon_entries(house.id)
    assert any(e.dri == "in-list@example.com" for e in entries)


def test_migration_adds_dri_column(tmp_path):
    """Verify that _migrate() adds dri column to existing tables."""
    db_path = tmp_path / "test_dri_migrate.db"

    # Create tables WITHOUT dri column using raw SQL + old schema
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS canon_domains (
            id VARCHAR(36) PRIMARY KEY,
            workspace_id VARCHAR(36) NOT NULL DEFAULT 'default',
            name VARCHAR(255) NOT NULL,
            source VARCHAR(50) DEFAULT 'manual',
            source_id VARCHAR(255),
            document_type VARCHAR(30) NOT NULL DEFAULT 'canon_domain',
            summary TEXT DEFAULT '',
            audience TEXT DEFAULT '',
            brand_personality TEXT DEFAULT '',
            positioning TEXT DEFAULT '',
            tagline VARCHAR(500) DEFAULT '',
            differentiation TEXT DEFAULT '',
            status VARCHAR(20) DEFAULT 'active',
            department VARCHAR(100) NOT NULL DEFAULT 'General',
            parent_domain_id VARCHAR(36),
            inheritance_policy VARCHAR(50) DEFAULT 'full',
            last_synced DATETIME,
            last_reviewed DATETIME
        );
        CREATE TABLE IF NOT EXISTS canon_entries (
            id VARCHAR(36) PRIMARY KEY,
            canon_domain_id VARCHAR(36) NOT NULL,
            section_type VARCHAR(50) NOT NULL DEFAULT 'voice',
            content TEXT NOT NULL DEFAULT '',
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            priority INTEGER NOT NULL DEFAULT 100,
            approved_by VARCHAR(255),
            approved_at DATETIME,
            source_chunk_id VARCHAR(255),
            content_tier VARCHAR(20),
            pillar_id INTEGER,
            variants TEXT DEFAULT '{}',
            personas TEXT DEFAULT '[]'
        );
    """)
    conn.close()

    # Run migration — should add dri to both tables
    s = Store(f"sqlite:///{db_path}")
    s._migrate()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("PRAGMA table_info(canon_domains)")
    cols = {row[1] for row in cursor.fetchall()}
    assert "dri" in cols, f"dri column missing from canon_domains: {cols}"
    cursor = conn.execute("PRAGMA table_info(canon_entries)")
    cols = {row[1] for row in cursor.fetchall()}
    assert "dri" in cols, f"dri column missing from canon_entries: {cols}"
    conn.close()


# ── C1: DRI changes log dri_transfer events to the review trail ─────────────

def test_set_domain_dri_logs_trail_event(store):
    s, house = store
    s.set_domain_dri(str(house.id), "carol@example.com", performed_by="tester")
    trail = s.get_review_trail(house.id)
    transfers = [t for t in trail if t["action"] == "dri_transfer"]
    assert len(transfers) == 1
    assert transfers[0]["performed_by"] == "tester"
    assert "alice@example.com" in transfers[0]["notes"]
    assert "carol@example.com" in transfers[0]["notes"]


def test_set_entry_dri_logs_trail_event(store):
    s, house = store
    entry = CanonEntry(
        id=uuid4(),
        canon_domain_id=house.id,
        section_type="headline",
        content="Entry for DRI trail",
        priority=1,
    )
    s.upsert_canon_entry(entry)
    s.set_entry_dri(str(entry.id), "dave@example.com", performed_by="tester")
    trail = s.get_entry_review_trail(str(entry.id))
    transfers = [t for t in trail if t["action"] == "dri_transfer"]
    assert len(transfers) == 1
    assert "(unassigned)" in transfers[0]["notes"]
    assert "dave@example.com" in transfers[0]["notes"]


# ── C2: DRI accountability summary ───────────────────────────────────────────

def test_dri_summary_groups_and_unowned(store):
    s, house = store  # house has dri alice@example.com
    orphan = CanonDomain(id=uuid4(), name="Orphan Domain", grounding_type="message_house")
    s.upsert_canon_domain(orphan)
    entry = CanonEntry(
        id=uuid4(),
        canon_domain_id=orphan.id,
        section_type="headline",
        content="Unowned entry",
        priority=1,
    )
    s.upsert_canon_entry(entry)

    summary = s.get_dri_summary()
    assert summary["unowned_count"] == 1
    assert summary["unowned"][0]["name"] == "Orphan Domain"
    assert summary["unowned"][0]["unowned_entry_count"] == 1
    assert "alice@example.com" in summary["by_dri"]
    owned = summary["by_dri"]["alice@example.com"]
    assert any(d["name"] == "DRI Test House" for d in owned)


def test_dri_summary_empty_store(tmp_path):
    s = Store(f"sqlite:///{tmp_path / 'empty_dri.db'}")
    s.init()
    summary = s.get_dri_summary()
    assert summary["unowned"] == []
    assert summary["by_dri"] == {}
