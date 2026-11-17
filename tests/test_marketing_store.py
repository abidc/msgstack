"""MarketingStore: brands, canon versions, tenant isolation."""

from datetime import date, datetime
from uuid import uuid4

import pytest

from src.marketing.models import (Approval, Brand, ContentItem, ContentStatus, ResultRecord, Schedule,
                                  VoiceCanon)
from src.marketing.store import MarketingStore, NotFound


@pytest.fixture
def store(tmp_path):
    return MarketingStore(f"sqlite:///{tmp_path / 'mkt.db'}").init()


def test_brand_roundtrip_and_workspace_filter(store):
    a = store.create_brand(Brand(name="A", workspace_id="ws1", weekly_quota={"linkedin": 2}))
    store.create_brand(Brand(name="B", workspace_id="ws2"))
    got = store.get_brand(a.id)
    assert got.name == "A" and got.weekly_quota == {"linkedin": 2} and got.autonomy.value == "approve_each"
    assert [b.name for b in store.list_brands("ws1")] == ["A"]
    assert len(store.list_brands()) == 2
    with pytest.raises(NotFound):
        store.get_brand(uuid4())


def test_canon_versions_are_appended_and_latest_wins(store):
    b = store.create_brand(Brand(name="A"))
    assert store.get_canon(b.id) is None
    v1 = store.save_canon(VoiceCanon(brand_id=b.id, one_liner="one"))
    v2 = store.save_canon(VoiceCanon(brand_id=b.id, one_liner="two", tone=["plain"]))
    assert (v1.version, v2.version) == (1, 2)
    latest = store.get_canon(b.id)
    assert latest.version == 2 and latest.one_liner == "two" and latest.tone == ["plain"]
    assert store.get_canon(b.id, version=1).one_liner == "one"
    with pytest.raises(NotFound):
        store.save_canon(VoiceCanon(brand_id=uuid4()))


def test_items_are_scoped_to_their_brand(store):
    a = store.create_brand(Brand(name="A"))
    b = store.create_brand(Brand(name="B"))
    item = store.save_item(ContentItem(brand_id=a.id, channel="linkedin", body="hello world text",
                                       slot_date=date(2026, 11, 16)))
    assert store.get_item(a.id, item.id).body == "hello world text"
    with pytest.raises(NotFound):
        store.get_item(b.id, item.id)
    assert store.list_items(b.id) == []
    assert [i.id for i in store.list_items(a.id, channel="linkedin", since=date(2026, 11, 16))] == [item.id]
    assert store.list_items(a.id, status="approved") == []


def test_item_update_preserves_gate_and_status(store):
    a = store.create_brand(Brand(name="A"))
    item = ContentItem(brand_id=a.id, channel="x", body="short post body")
    store.save_item(item)
    item.status = ContentStatus.APPROVED
    item.body = "edited body text"
    store.save_item(item)
    got = store.get_item(a.id, item.id)
    assert got.status == ContentStatus.APPROVED and got.body == "edited body text"
    assert got.gate.clean is True


def test_approvals_schedules_results_roundtrip(store):
    a = store.create_brand(Brand(name="A"))
    item = store.save_item(ContentItem(brand_id=a.id, channel="newsletter", body="issue body text"))
    store.save_approval(Approval(brand_id=a.id, content_id=item.id, decision="approve", decided_by="abid"))
    sched = store.save_schedule(Schedule(brand_id=a.id, content_id=item.id, channel="newsletter",
                                         publish_at=datetime(2026, 11, 19, 9, 0), destination="listmonk"))
    assert store.get_schedule_for(a.id, item.id).destination == "listmonk"
    assert [s.id for s in store.list_schedules(a.id, status="scheduled")] == [sched.id]
    sched.status = "published"
    store.save_schedule(sched)
    assert store.list_schedules(a.id, status="scheduled") == []
    store.save_result(ResultRecord(brand_id=a.id, content_id=item.id, channel="newsletter",
                                   published_at=datetime(2026, 11, 19, 9, 5), external_ref="camp-7",
                                   metrics={"delivered": 71}))
    res = store.list_results(a.id)
    assert len(res) == 1 and res[0].metrics == {"delivered": 71}
    assert store.list_results(a.id, since=datetime(2026, 11, 20)) == []
    assert store.list_approvals(a.id, item.id)[0].decided_by == "abid"
