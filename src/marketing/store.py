"""SQLAlchemy persistence for the marketing slice.

Separate declarative base and ``mkt_`` table prefix so this can live in the
same SQLite/Postgres database as the core canon tables without touching
``src/store.py``'s 4,000-line migration history. ``MarketingStore`` accepts a
URL (tests) or an existing engine (production: the core store's engine).

Tenant rule: every read of a child row goes through ``_owned(brand_id, ...)``,
which raises :class:`NotFound` when the row belongs to another brand. A caller
can never see another tenant's content by guessing an id.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (JSON, Boolean, Date, DateTime, Integer, String, Text, create_engine,
                        select)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .models import (Approval, Brand, ContentItem, ContentStatus, GateResult, ResultRecord,
                     Schedule, VoiceCanon)


class NotFound(LookupError):
    pass


class Base(DeclarativeBase):
    pass


class BrandModel(Base):
    __tablename__ = "mkt_brands"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="default", index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), default="")
    owner: Mapped[str] = mapped_column(String(255), default="")
    kind: Mapped[str] = mapped_column(String(30), default="solo")
    autonomy: Mapped[str] = mapped_column(String(30), default="approve_each")
    weekly_quota: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class VoiceCanonModel(Base):
    __tablename__ = "mkt_voice_canons"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    brand_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)   # the VoiceCanon minus id/brand/version
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ContentItemModel(Base):
    __tablename__ = "mkt_content_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    brand_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    canon_version: Mapped[int] = mapped_column(Integer, default=1)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    slot_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    topic: Mapped[str] = mapped_column(String(500), default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    gate: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_by: Mapped[str] = mapped_column(String(100), default="manual")
    rewrite_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ApprovalModel(Base):
    __tablename__ = "mkt_approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    brand_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    content_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    decided_by: Mapped[str] = mapped_column(String(255), default="")
    override_hard: Mapped[bool] = mapped_column(Boolean, default=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ScheduleModel(Base):
    __tablename__ = "mkt_schedules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    brand_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    content_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    publish_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    destination: Mapped[str] = mapped_column(String(50), default="manual")
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    external_ref: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ResultModel(Base):
    __tablename__ = "mkt_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    brand_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    content_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    external_ref: Mapped[str] = mapped_column(String(500), default="")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


def _s(v) -> str:
    return str(v)


class MarketingStore:
    def __init__(self, url_or_engine: str | Engine):
        if isinstance(url_or_engine, str):
            kw = {"connect_args": {"check_same_thread": False}} if url_or_engine.startswith("sqlite") else {}
            self.engine = create_engine(url_or_engine, **kw)
        else:
            self.engine = url_or_engine

    def init(self) -> "MarketingStore":
        Base.metadata.create_all(self.engine)
        return self

    def _session(self) -> Session:
        return Session(self.engine, expire_on_commit=False)

    # ------------------------------------------------------------------ brands
    def create_brand(self, brand: Brand) -> Brand:
        with self._session() as s:
            s.add(BrandModel(id=_s(brand.id), workspace_id=brand.workspace_id, name=brand.name,
                             slug=brand.slug, owner=brand.owner, kind=brand.kind,
                             autonomy=brand.autonomy.value, weekly_quota=brand.weekly_quota,
                             created_at=brand.created_at))
            s.commit()
        return brand

    def get_brand(self, brand_id: UUID | str) -> Brand:
        with self._session() as s:
            row = s.get(BrandModel, _s(brand_id))
            if row is None:
                raise NotFound(f"brand {brand_id} not found")
            return self._brand(row)

    def list_brands(self, workspace_id: Optional[str] = None) -> list[Brand]:
        with self._session() as s:
            q = select(BrandModel).order_by(BrandModel.created_at)
            if workspace_id:
                q = q.where(BrandModel.workspace_id == workspace_id)
            return [self._brand(r) for r in s.scalars(q)]

    def update_brand(self, brand: Brand) -> Brand:
        with self._session() as s:
            row = s.get(BrandModel, _s(brand.id))
            if row is None:
                raise NotFound(f"brand {brand.id} not found")
            row.name, row.slug, row.owner, row.kind = brand.name, brand.slug, brand.owner, brand.kind
            row.autonomy, row.weekly_quota = brand.autonomy.value, brand.weekly_quota
            s.commit()
        return brand

    @staticmethod
    def _brand(r: BrandModel) -> Brand:
        return Brand(id=UUID(r.id), workspace_id=r.workspace_id, name=r.name, slug=r.slug, owner=r.owner,
                     kind=r.kind, autonomy=r.autonomy, weekly_quota=r.weekly_quota or {}, created_at=r.created_at)

    # ------------------------------------------------------------------ canon
    def save_canon(self, canon: VoiceCanon) -> VoiceCanon:
        """Append a new version. Versions are immutable; `version` is assigned here."""
        with self._session() as s:
            if s.get(BrandModel, _s(canon.brand_id)) is None:
                raise NotFound(f"brand {canon.brand_id} not found")
            latest = s.scalars(select(VoiceCanonModel).where(VoiceCanonModel.brand_id == _s(canon.brand_id))
                               .order_by(VoiceCanonModel.version.desc())).first()
            canon.version = (latest.version + 1) if latest else 1
            payload = canon.model_dump(mode="json", exclude={"id", "brand_id", "version", "created_at"})
            s.add(VoiceCanonModel(id=_s(canon.id), brand_id=_s(canon.brand_id), version=canon.version,
                                  payload=payload, created_at=canon.created_at))
            s.commit()
        return canon

    def get_canon(self, brand_id: UUID | str, version: Optional[int] = None) -> Optional[VoiceCanon]:
        with self._session() as s:
            q = select(VoiceCanonModel).where(VoiceCanonModel.brand_id == _s(brand_id))
            if version is not None:
                q = q.where(VoiceCanonModel.version == version)
            row = s.scalars(q.order_by(VoiceCanonModel.version.desc())).first()
            if row is None:
                return None
            return VoiceCanon(id=UUID(row.id), brand_id=UUID(row.brand_id), version=row.version,
                              created_at=row.created_at, **row.payload)

    # ------------------------------------------------------------------ content
    def save_item(self, item: ContentItem) -> ContentItem:
        with self._session() as s:
            row = s.get(ContentItemModel, _s(item.id))
            data = dict(brand_id=_s(item.brand_id), canon_version=item.canon_version, channel=item.channel,
                        slot_date=item.slot_date, topic=item.topic, body=item.body, status=item.status.value,
                        gate=item.gate.model_dump(mode="json"), generated_by=item.generated_by,
                        rewrite_count=item.rewrite_count, created_at=item.created_at, updated_at=item.updated_at)
            if row is None:
                s.add(ContentItemModel(id=_s(item.id), **data))
            else:
                for k, v in data.items():
                    setattr(row, k, v)
            s.commit()
        return item

    def get_item(self, brand_id: UUID | str, content_id: UUID | str) -> ContentItem:
        with self._session() as s:
            row = s.get(ContentItemModel, _s(content_id))
            if row is None or row.brand_id != _s(brand_id):
                raise NotFound(f"content {content_id} not found for brand {brand_id}")
            return self._item(row)

    def list_items(self, brand_id: UUID | str, status: Optional[str] = None, channel: Optional[str] = None,
                   since: Optional[date] = None, until: Optional[date] = None, limit: int = 200) -> list[ContentItem]:
        with self._session() as s:
            q = select(ContentItemModel).where(ContentItemModel.brand_id == _s(brand_id))
            if status:
                q = q.where(ContentItemModel.status == status)
            if channel:
                q = q.where(ContentItemModel.channel == channel)
            if since:
                q = q.where(ContentItemModel.slot_date >= since)
            if until:
                q = q.where(ContentItemModel.slot_date <= until)
            q = q.order_by(ContentItemModel.slot_date, ContentItemModel.created_at).limit(limit)
            return [self._item(r) for r in s.scalars(q)]

    @staticmethod
    def _item(r: ContentItemModel) -> ContentItem:
        return ContentItem(id=UUID(r.id), brand_id=UUID(r.brand_id), canon_version=r.canon_version,
                           channel=r.channel, slot_date=r.slot_date, topic=r.topic, body=r.body,
                           status=ContentStatus(r.status), gate=GateResult(**(r.gate or {})),
                           generated_by=r.generated_by, rewrite_count=r.rewrite_count,
                           created_at=r.created_at, updated_at=r.updated_at)

    # ------------------------------------------------------------------ approvals
    def save_approval(self, a: Approval) -> Approval:
        with self._session() as s:
            s.add(ApprovalModel(id=_s(a.id), brand_id=_s(a.brand_id), content_id=_s(a.content_id),
                                decision=a.decision, reason=a.reason, decided_by=a.decided_by,
                                override_hard=a.override_hard, decided_at=a.decided_at))
            s.commit()
        return a

    def list_approvals(self, brand_id: UUID | str, content_id: Optional[UUID | str] = None) -> list[Approval]:
        with self._session() as s:
            q = select(ApprovalModel).where(ApprovalModel.brand_id == _s(brand_id))
            if content_id:
                q = q.where(ApprovalModel.content_id == _s(content_id))
            return [Approval(id=UUID(r.id), brand_id=UUID(r.brand_id), content_id=UUID(r.content_id),
                             decision=r.decision, reason=r.reason, decided_by=r.decided_by,
                             override_hard=r.override_hard, decided_at=r.decided_at)
                    for r in s.scalars(q.order_by(ApprovalModel.decided_at))]

    # ------------------------------------------------------------------ schedules
    def save_schedule(self, sch: Schedule) -> Schedule:
        with self._session() as s:
            row = s.get(ScheduleModel, _s(sch.id))
            data = dict(brand_id=_s(sch.brand_id), content_id=_s(sch.content_id), channel=sch.channel,
                        publish_at=sch.publish_at, destination=sch.destination, status=sch.status,
                        external_ref=sch.external_ref, created_at=sch.created_at)
            if row is None:
                s.add(ScheduleModel(id=_s(sch.id), **data))
            else:
                for k, v in data.items():
                    setattr(row, k, v)
            s.commit()
        return sch

    def get_schedule_for(self, brand_id: UUID | str, content_id: UUID | str) -> Optional[Schedule]:
        with self._session() as s:
            row = s.scalars(select(ScheduleModel).where(ScheduleModel.brand_id == _s(brand_id),
                                                        ScheduleModel.content_id == _s(content_id))).first()
            return self._sched(row) if row else None

    def list_schedules(self, brand_id: UUID | str, status: Optional[str] = None) -> list[Schedule]:
        with self._session() as s:
            q = select(ScheduleModel).where(ScheduleModel.brand_id == _s(brand_id))
            if status:
                q = q.where(ScheduleModel.status == status)
            return [self._sched(r) for r in s.scalars(q.order_by(ScheduleModel.publish_at))]

    @staticmethod
    def _sched(r: ScheduleModel) -> Schedule:
        return Schedule(id=UUID(r.id), brand_id=UUID(r.brand_id), content_id=UUID(r.content_id), channel=r.channel,
                        publish_at=r.publish_at, destination=r.destination, status=r.status,
                        external_ref=r.external_ref, created_at=r.created_at)

    # ------------------------------------------------------------------ results
    def save_result(self, res: ResultRecord) -> ResultRecord:
        with self._session() as s:
            s.add(ResultModel(id=_s(res.id), brand_id=_s(res.brand_id), content_id=_s(res.content_id),
                              channel=res.channel, published_at=res.published_at, external_ref=res.external_ref,
                              metrics=res.metrics, captured_at=res.captured_at))
            s.commit()
        return res

    def list_results(self, brand_id: UUID | str, since: Optional[datetime] = None) -> list[ResultRecord]:
        with self._session() as s:
            q = select(ResultModel).where(ResultModel.brand_id == _s(brand_id))
            if since:
                q = q.where(ResultModel.published_at >= since)
            return [ResultRecord(id=UUID(r.id), brand_id=UUID(r.brand_id), content_id=UUID(r.content_id),
                                 channel=r.channel, published_at=r.published_at, external_ref=r.external_ref,
                                 metrics=r.metrics or {}, captured_at=r.captured_at)
                    for r in s.scalars(q.order_by(ResultModel.published_at))]


# Module-level singleton, resolved lazily so importing this package never opens a DB.
_instance: Optional[MarketingStore] = None


def get_marketing_store() -> MarketingStore:
    """Return the shared MarketingStore, bound to the core store's engine (same DB file)."""
    global _instance
    if _instance is None:
        from src.store import get_store
        _instance = MarketingStore(get_store().engine).init()
    return _instance


def set_marketing_store(store: Optional[MarketingStore]) -> None:
    """Test hook / explicit wiring."""
    global _instance
    _instance = store
