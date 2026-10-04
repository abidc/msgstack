from agent.identity import IdentityStore


def test_resolve_falls_back_to_platform_prefixed_id_when_unmapped(tmp_path):
    store = IdentityStore(db_url=f"sqlite:///{tmp_path}/identity.db")
    assert store.resolve("slack", "U999") == "slack:U999"


def test_upsert_then_resolve_returns_display_name(tmp_path):
    store = IdentityStore(db_url=f"sqlite:///{tmp_path}/identity.db")
    store.upsert("slack", "U1", display_name="Abid Chaudhry")
    assert store.resolve("slack", "U1") == "Abid Chaudhry"


def test_upsert_falls_back_to_email_when_no_display_name(tmp_path):
    store = IdentityStore(db_url=f"sqlite:///{tmp_path}/identity.db")
    store.upsert("teams", "T1", email="abid@example.com")
    assert store.resolve("teams", "T1") == "abid@example.com"


def test_upsert_is_idempotent_and_updates_existing_row(tmp_path):
    store = IdentityStore(db_url=f"sqlite:///{tmp_path}/identity.db")
    store.upsert("slack", "U1", display_name="Old Name")
    store.upsert("slack", "U1", display_name="New Name")
    assert store.resolve("slack", "U1") == "New Name"


def test_platforms_are_independent_namespaces(tmp_path):
    store = IdentityStore(db_url=f"sqlite:///{tmp_path}/identity.db")
    store.upsert("slack", "SAME_ID", display_name="Slack Person")
    store.upsert("teams", "SAME_ID", display_name="Teams Person")
    assert store.resolve("slack", "SAME_ID") == "Slack Person"
    assert store.resolve("teams", "SAME_ID") == "Teams Person"
