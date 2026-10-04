import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from src.models import QueryAuditLog
from src.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(f"sqlite:///{tmp_path / 'test_audit.db'}")
    s.init()
    return s


def test_log_and_retrieve(store):
    entry = QueryAuditLog(
        id=uuid4(),
        session_id="sess-1",
        user_id="user-1",
        query_text="What is our brand voice?",
        model_used="gpt-4o",
        artifacts_used=["art-1", "art-2"],
        entries_used=["ent-1"],
        latency_ms=123.4,
        tokens_used=500,
        source="chat",
    )
    store.log_query(entry)
    logs = store.get_query_log(limit=10)
    assert len(logs) == 1
    assert logs[0]["query_text"] == "What is our brand voice?"
    assert logs[0]["artifacts_used"] == ["art-1", "art-2"]
    assert logs[0]["entries_used"] == ["ent-1"]
    assert logs[0]["latency_ms"] == 123.4
    assert logs[0]["tokens_used"] == 500
    assert logs[0]["source"] == "chat"
    assert logs[0]["session_id"] == "sess-1"
    assert logs[0]["user_id"] == "user-1"


def test_log_with_minimal_fields(store):
    entry = QueryAuditLog(
        id=uuid4(),
        query_text="Hello",
    )
    store.log_query(entry)
    logs = store.get_query_log(limit=10)
    assert len(logs) == 1
    assert logs[0]["query_text"] == "Hello"
    assert logs[0]["source"] == ""
    assert logs[0]["latency_ms"] == 0.0


def test_get_query_log_limit(store):
    for i in range(5):
        store.log_query(QueryAuditLog(id=uuid4(), query_text=f"Q{i}"))
    assert len(store.get_query_log(limit=3)) == 3
    assert len(store.get_query_log(limit=10)) == 5


def test_get_query_log_filter_source(store):
    store.log_query(QueryAuditLog(id=uuid4(), query_text="A", source="chat"))
    store.log_query(QueryAuditLog(id=uuid4(), query_text="B", source="search"))
    store.log_query(QueryAuditLog(id=uuid4(), query_text="C", source="generator"))
    chat_logs = store.get_query_log(limit=10, source="chat")
    assert len(chat_logs) == 1
    assert chat_logs[0]["source"] == "chat"


def test_clean_query_log(store):
    old = QueryAuditLog(
        id=uuid4(),
        query_text="Old query",
        timestamp=datetime.now() - timedelta(days=200),
    )
    new = QueryAuditLog(
        id=uuid4(),
        query_text="Recent query",
        timestamp=datetime.now(),
    )
    store.log_query(old)
    store.log_query(new)
    deleted = store.clean_query_log(older_than_days=90)
    assert deleted == 1
    logs = store.get_query_log(limit=10)
    assert len(logs) == 1
    assert logs[0]["query_text"] == "Recent query"


def test_clean_query_log_no_delete(store):
    entry = QueryAuditLog(
        id=uuid4(),
        query_text="Recent",
        timestamp=datetime.now(),
    )
    store.log_query(entry)
    deleted = store.clean_query_log(older_than_days=90)
    assert deleted == 0
    assert len(store.get_query_log(limit=10)) == 1


def test_get_query_log_empty(store):
    assert store.get_query_log(limit=10) == []


def test_clean_query_log_empty(store):
    assert store.clean_query_log(older_than_days=30) == 0


def test_domain_ids_and_confidence_roundtrip(store):
    dom = str(uuid4())
    store.log_query(QueryAuditLog(
        id=uuid4(), query_text="Q", domain_ids=[dom], top_confidence=0.87, source="mcp:search_canon",
    ))
    logs = store.get_query_log(limit=10)
    assert logs[0]["domain_ids"] == [dom]
    assert logs[0]["top_confidence"] == 0.87


def test_filter_by_caller(store):
    store.log_query(QueryAuditLog(id=uuid4(), query_text="A", user_id="alice"))
    store.log_query(QueryAuditLog(id=uuid4(), query_text="B", user_id="bob"))
    logs = store.get_query_log(limit=10, caller="alice")
    assert len(logs) == 1
    assert logs[0]["user_id"] == "alice"


def test_filter_by_domain_id(store):
    dom_a, dom_b = str(uuid4()), str(uuid4())
    store.log_query(QueryAuditLog(id=uuid4(), query_text="A", domain_ids=[dom_a]))
    store.log_query(QueryAuditLog(id=uuid4(), query_text="B", domain_ids=[dom_b]))
    logs = store.get_query_log(limit=10, domain_id=dom_a)
    assert len(logs) == 1
    assert logs[0]["query_text"] == "A"


def test_filter_by_since(store):
    store.log_query(QueryAuditLog(id=uuid4(), query_text="Old", timestamp=datetime.now() - timedelta(days=10)))
    store.log_query(QueryAuditLog(id=uuid4(), query_text="New", timestamp=datetime.now()))
    logs = store.get_query_log(limit=10, since=datetime.now() - timedelta(days=1))
    assert len(logs) == 1
    assert logs[0]["query_text"] == "New"


# ── A2: search paths actually write audit rows ──────────────────────────────

def _fake_grounding_response(domain_id):
    from src.models import GroundingResponse, GroundingResult, GroundingContext
    return GroundingResponse(
        results=[
            GroundingResult(
                chunk_id="chunk-1",
                content="Approved claim",
                section_type="headline",
                priority=1,
                persona=None,
                channel="all",
                source={"house_id": domain_id, "house_name": "Test"},
                confidence=0.91,
            )
        ],
        grounding_context=GroundingContext(),
    )


def test_search_messaging_writes_audit_row(store, monkeypatch):
    from unittest.mock import MagicMock
    from src.grounding import tools

    domain_id = str(uuid4())
    engine = MagicMock()
    engine.search.return_value = _fake_grounding_response(domain_id)
    monkeypatch.setattr(tools, "_get_engine", lambda workspace_id=None: engine)
    monkeypatch.setattr(tools, "_get_store", lambda: store)

    tools.search_messaging(query="what is our headline?")

    logs = store.get_query_log(limit=10)
    assert len(logs) == 1
    row = logs[0]
    assert row["query_text"] == "what is our headline?"
    assert row["entries_used"] == ["chunk-1"]
    assert row["domain_ids"] == [domain_id]
    assert row["top_confidence"] == 0.91
    assert row["source"] == "mcp:search_canon"
    assert row["user_id"] == "mcp-session"


def test_audit_failure_does_not_break_search(store, monkeypatch):
    from unittest.mock import MagicMock
    from src.grounding import tools

    engine = MagicMock()
    engine.search.return_value = _fake_grounding_response(str(uuid4()))
    monkeypatch.setattr(tools, "_get_engine", lambda workspace_id=None: engine)

    broken_store = MagicMock()
    broken_store.log_query.side_effect = RuntimeError("db locked")
    monkeypatch.setattr(tools, "_get_store", lambda: broken_store)

    response = tools.search_messaging(query="still works?")
    assert len(response.results) == 1
