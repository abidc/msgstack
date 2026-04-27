"""SQLite / PostgreSQL-backed message house storage."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Self
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from src.models import Channel, HouseStatus, KeyMessage, MessageHouse, Persona, SectionType

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Module-level singleton — set by init_store() called from web_app startup
_store_instance: "Store | None" = None


def get_store() -> "Store":
    """Return the global Store singleton (must call init_store first)."""
    if _store_instance is None:
        raise RuntimeError("Store not initialized — call init_store() first")
    return _store_instance


def init_store(db_url: str | None = None) -> "Store":
    """Create and initialize the global Store singleton."""
    global _store_instance
    from src.config import settings
    url = db_url or settings.database_url
    _store_instance = Store(url)
    _store_instance.init()
    return _store_instance


def _to_db(data: dict) -> dict:
    return {k: str(v) if isinstance(v, UUID) else v for k, v in data.items()}


class Base(DeclarativeBase):
    pass


class WorkspaceModel(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    max_token_budget: Mapped[int] = mapped_column(Integer, default=0)  # 0 = unlimited
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ApiKeyModel(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TokenUsageModel(Base):
    __tablename__ = "token_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class HouseModel(Base):
    __tablename__ = "message_houses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="default")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str] = mapped_column(String(1000), default="")
    audience: Mapped[str] = mapped_column(String(500), default="")
    brand_personality: Mapped[str] = mapped_column(String(1000), default="")
    positioning: Mapped[str] = mapped_column(String(2000), default="")
    tagline: Mapped[str] = mapped_column(String(500), default="")
    differentiation: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    last_synced: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    key_messages: Mapped[list["KeyMessageModel"]] = relationship(
        back_populates="message_house", cascade="all, delete-orphan"
    )
    personas: Mapped[list["PersonaModel"]] = relationship(
        back_populates="message_house", cascade="all, delete-orphan"
    )


class KeyMessageModel(Base):
    __tablename__ = "key_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    message_house_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("message_houses.id"), nullable=False
    )
    section_type: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(String(2000), nullable=False)
    variants: Mapped[dict] = mapped_column(JSON, default=dict)
    personas: Mapped[list] = mapped_column(JSON, default=list)
    channels: Mapped[list] = mapped_column(JSON, default=["all"])
    source_chunk_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message_house: Mapped["HouseModel"] = relationship(back_populates="key_messages")


class PersonaModel(Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    message_house_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("message_houses.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="")
    pain_points: Mapped[list] = mapped_column(JSON, default=list)
    buying_triggers: Mapped[list] = mapped_column(JSON, default=list)
    objections: Mapped[list] = mapped_column(JSON, default=list)

    message_house: Mapped["HouseModel"] = relationship(back_populates="personas")


class SnapshotModel(Base):
    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    house_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("message_houses.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), default="")
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ArtifactHistoryModel(Base):
    __tablename__ = "artifact_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    house_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("message_houses.id"), nullable=False
    )
    skill_id: Mapped[str] = mapped_column(String(100), nullable=False)
    house_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sections_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Store:
    def __init__(self, db_url: str | Path = "sqlite:///msgstack.db"):
        # Accept either a full SQLAlchemy URL or a bare file path (back-compat)
        url = str(db_url)
        if not url.startswith(("sqlite", "postgresql", "mysql", "postgres")):
            url = f"sqlite:///{url}"
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, echo=False, connect_args=connect_args)
        self.session_factory = sessionmaker(bind=self.engine)

    def init(self) -> None:
        Base.metadata.create_all(self.engine)
        self._ensure_default_workspace()

    def _ensure_default_workspace(self) -> None:
        with self.session() as s:
            existing = s.query(WorkspaceModel).filter(WorkspaceModel.slug == "default").first()
            if not existing:
                s.add(WorkspaceModel(
                    id="default",
                    slug="default",
                    name="Default Workspace",
                    max_token_budget=0,
                    created_at=_now(),
                ))
                s.commit()

    def session(self) -> Session:
        return self.session_factory()

    def upsert_house(self, house: MessageHouse, workspace_id: str = "default") -> None:
        with self.session() as s:
            existing = s.get(HouseModel, str(house.id))
            if existing:
                for k, v in _to_db(house.model_dump()).items():
                    if k != "id":
                        setattr(existing, k, v)
                # Don't change workspace on update unless explicitly passed
            else:
                data = _to_db(house.model_dump())
                data["workspace_id"] = workspace_id
                s.add(HouseModel(**data))
            s.commit()

    def get_house(self, house_id: UUID) -> MessageHouse | None:
        with self.session() as s:
            row = s.get(HouseModel, str(house_id))
            if not row:
                return None
            return _house_from_row(row)

    def get_house_by_name(self, name: str) -> MessageHouse | None:
        with self.session() as s:
            row = s.query(HouseModel).filter(HouseModel.name == name).first()
            if not row:
                return None
            return _house_from_row(row)

    def upsert_key_message(self, msg: KeyMessage) -> None:
        with self.session() as s:
            existing = s.get(KeyMessageModel, str(msg.id))
            if existing:
                for k, v in _to_db(msg.model_dump()).items():
                    if k != "id":
                        setattr(existing, k, v)
            else:
                s.add(KeyMessageModel(**_to_db(msg.model_dump())))
            s.commit()

    def get_key_messages(self, house_id: UUID) -> list[KeyMessage]:
        with self.session() as s:
            rows = (
                s.query(KeyMessageModel)
                .filter(KeyMessageModel.message_house_id == str(house_id))
                .order_by(KeyMessageModel.priority)
                .all()
            )
            return [_msg_from_row(r) for r in rows]

    def get_key_message(self, msg_id: UUID) -> KeyMessage | None:
        with self.session() as s:
            row = s.get(KeyMessageModel, str(msg_id))
            return _msg_from_row(row) if row else None

    def get_persona(self, persona_id: UUID) -> Persona | None:
        with self.session() as s:
            row = s.get(PersonaModel, str(persona_id))
            return _persona_from_row(row) if row else None

    def upsert_persona(self, persona: Persona) -> None:
        with self.session() as s:
            existing = s.get(PersonaModel, str(persona.id))
            if existing:
                for k, v in _to_db(persona.model_dump()).items():
                    if k != "id":
                        setattr(existing, k, v)
            else:
                s.add(PersonaModel(**_to_db(persona.model_dump())))
            s.commit()

    def get_personas(self, house_id: UUID) -> list[Persona]:
        with self.session() as s:
            rows = (
                s.query(PersonaModel)
                .filter(PersonaModel.message_house_id == str(house_id))
                .all()
            )
            return [_persona_from_row(r) for r in rows]

    def delete_house(self, house_id: UUID) -> bool:
        with self.session() as s:
            row = s.get(HouseModel, str(house_id))
            if row:
                s.delete(row)
                s.commit()
                return True
            return False

    def delete_key_message(self, msg_id: UUID) -> bool:
        with self.session() as s:
            row = s.get(KeyMessageModel, str(msg_id))
            if row:
                s.delete(row)
                s.commit()
                return True
            return False

    def delete_persona(self, persona_id: UUID) -> bool:
        with self.session() as s:
            row = s.get(PersonaModel, str(persona_id))
            if row:
                s.delete(row)
                s.commit()
                return True
            return False

    # --- Snapshots ---

    def create_snapshot(self, house_id: UUID, label: str = "") -> dict:
        house = self.get_house(house_id)
        if not house:
            raise ValueError(f"House {house_id} not found")
        messages = self.get_key_messages(house_id)
        personas = self.get_personas(house_id)
        snapshot_data = {
            "house": {
                "id": str(house.id),
                "name": house.name,
                "source": house.source,
                "summary": house.summary,
                "audience": house.audience,
                "brand_personality": house.brand_personality,
                "positioning": house.positioning,
                "tagline": house.tagline,
                "differentiation": house.differentiation,
                "status": str(house.status),
            },
            "messages": [
                {
                    "id": str(m.id),
                    "section_type": str(m.section_type),
                    "priority": m.priority,
                    "content": m.content,
                    "variants": m.variants,
                    "personas": m.personas,
                    "channels": [str(c) for c in m.channels],
                }
                for m in messages
            ],
            "personas": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "description": p.description,
                    "pain_points": p.pain_points,
                    "buying_triggers": p.buying_triggers,
                    "objections": p.objections,
                }
                for p in personas
            ],
        }
        snap_id = str(uuid4())
        now = _now()
        with self.session() as s:
            s.add(SnapshotModel(
                id=snap_id,
                house_id=str(house_id),
                label=label or f"Snapshot {now.strftime('%Y-%m-%d %H:%M')}",
                snapshot_json=snapshot_data,
                created_at=now,
            ))
            s.commit()
        return {"id": snap_id, "house_id": str(house_id), "label": label, "created_at": now.isoformat()}

    def list_snapshots(self, house_id: UUID) -> list[dict]:
        with self.session() as s:
            rows = (
                s.query(SnapshotModel)
                .filter(SnapshotModel.house_id == str(house_id))
                .order_by(SnapshotModel.created_at.desc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "house_id": r.house_id,
                    "label": r.label,
                    "created_at": r.created_at.isoformat(),
                    "message_count": len(r.snapshot_json.get("messages", [])),
                    "persona_count": len(r.snapshot_json.get("personas", [])),
                }
                for r in rows
            ]

    def get_snapshot(self, snapshot_id: UUID) -> dict | None:
        with self.session() as s:
            row = s.get(SnapshotModel, str(snapshot_id))
            if not row:
                return None
            return {
                "id": row.id,
                "house_id": row.house_id,
                "label": row.label,
                "created_at": row.created_at.isoformat(),
                "snapshot_json": row.snapshot_json,
            }

    def delete_snapshot(self, snapshot_id: UUID) -> bool:
        with self.session() as s:
            row = s.get(SnapshotModel, str(snapshot_id))
            if row:
                s.delete(row)
                s.commit()
                return True
            return False

    # --- Artifact History ---

    def save_artifact(self, house_id: UUID, skill_id: str, house_name: str,
                      sections: dict, raw_content: str = "") -> dict:
        art_id = str(uuid4())
        now = _now()
        with self.session() as s:
            s.add(ArtifactHistoryModel(
                id=art_id,
                house_id=str(house_id),
                skill_id=skill_id,
                house_name=house_name,
                sections_json=sections,
                raw_content=raw_content,
                created_at=now,
            ))
            s.commit()
        return {"id": art_id, "house_id": str(house_id), "skill_id": skill_id, "created_at": now.isoformat()}

    def list_artifacts(self, house_id: UUID) -> list[dict]:
        with self.session() as s:
            rows = (
                s.query(ArtifactHistoryModel)
                .filter(ArtifactHistoryModel.house_id == str(house_id))
                .order_by(ArtifactHistoryModel.created_at.desc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "house_id": r.house_id,
                    "skill_id": r.skill_id,
                    "house_name": r.house_name,
                    "created_at": r.created_at.isoformat(),
                    "section_count": len(r.sections_json),
                }
                for r in rows
            ]

    def get_artifact(self, artifact_id: UUID) -> dict | None:
        with self.session() as s:
            row = s.get(ArtifactHistoryModel, str(artifact_id))
            if not row:
                return None
            return {
                "id": row.id,
                "house_id": row.house_id,
                "skill_id": row.skill_id,
                "house_name": row.house_name,
                "sections": row.sections_json,
                "raw_content": row.raw_content,
                "created_at": row.created_at.isoformat(),
            }


    # --- Workspaces ---

    def list_workspaces(self) -> list[dict]:
        with self.session() as s:
            rows = s.query(WorkspaceModel).all()
            return [{"id": r.id, "slug": r.slug, "name": r.name,
                     "max_token_budget": r.max_token_budget,
                     "created_at": r.created_at.isoformat()} for r in rows]

    def get_workspace(self, workspace_id: str) -> dict | None:
        with self.session() as s:
            row = s.get(WorkspaceModel, workspace_id)
            if not row:
                row = s.query(WorkspaceModel).filter(WorkspaceModel.slug == workspace_id).first()
            if not row:
                return None
            return {"id": row.id, "slug": row.slug, "name": row.name,
                    "max_token_budget": row.max_token_budget,
                    "created_at": row.created_at.isoformat()}

    def create_workspace(self, slug: str, name: str, max_token_budget: int = 0) -> dict:
        ws_id = str(uuid4())
        now = _now()
        with self.session() as s:
            s.add(WorkspaceModel(id=ws_id, slug=slug, name=name,
                                 max_token_budget=max_token_budget, created_at=now))
            s.commit()
        return {"id": ws_id, "slug": slug, "name": name,
                "max_token_budget": max_token_budget, "created_at": now.isoformat()}

    def update_workspace(self, workspace_id: str, **kwargs) -> dict | None:
        with self.session() as s:
            row = s.get(WorkspaceModel, workspace_id)
            if not row:
                return None
            for k, v in kwargs.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            s.commit()
            return {"id": row.id, "slug": row.slug, "name": row.name,
                    "max_token_budget": row.max_token_budget}

    # --- API Keys ---

    def create_api_key(self, key_hash: str, name: str, workspace_id: str,
                       scopes: list[str]) -> dict:
        key_id = str(uuid4())
        now = _now()
        with self.session() as s:
            s.add(ApiKeyModel(id=key_id, key_hash=key_hash, name=name,
                              workspace_id=workspace_id, scopes=scopes,
                              is_active=True, created_at=now))
            s.commit()
        return {"id": key_id, "name": name, "workspace_id": workspace_id,
                "scopes": scopes, "is_active": True, "created_at": now.isoformat()}

    def list_api_keys(self, workspace_id: str | None = None) -> list[dict]:
        with self.session() as s:
            q = s.query(ApiKeyModel)
            if workspace_id:
                q = q.filter(ApiKeyModel.workspace_id == workspace_id)
            rows = q.order_by(ApiKeyModel.created_at.desc()).all()
            return [{"id": r.id, "name": r.name, "workspace_id": r.workspace_id,
                     "scopes": r.scopes, "is_active": r.is_active,
                     "created_at": r.created_at.isoformat(),
                     "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None}
                    for r in rows]

    def get_api_key_by_hash(self, key_hash: str) -> dict | None:
        with self.session() as s:
            row = s.query(ApiKeyModel).filter(ApiKeyModel.key_hash == key_hash).first()
            if not row:
                return None
            return {"id": row.id, "name": row.name, "workspace_id": row.workspace_id,
                    "scopes": row.scopes, "is_active": row.is_active,
                    "key_hash": row.key_hash}

    def revoke_api_key(self, key_id: str) -> bool:
        with self.session() as s:
            row = s.get(ApiKeyModel, key_id)
            if not row:
                return False
            row.is_active = False
            s.commit()
            return True

    def touch_api_key(self, key_id: str) -> None:
        with self.session() as s:
            row = s.get(ApiKeyModel, key_id)
            if row:
                row.last_used_at = _now()
                s.commit()

    # --- Token Usage ---

    def record_token_usage(self, workspace_id: str, endpoint: str, model: str,
                           input_tokens: int, output_tokens: int, cost_usd: float) -> None:
        with self.session() as s:
            s.add(TokenUsageModel(
                id=str(uuid4()),
                workspace_id=workspace_id,
                endpoint=endpoint,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                created_at=_now(),
            ))
            s.commit()

    def get_token_usage_summary(self, workspace_id: str | None = None) -> dict:
        with self.session() as s:
            q = s.query(TokenUsageModel)
            if workspace_id:
                q = q.filter(TokenUsageModel.workspace_id == workspace_id)
            rows = q.all()
            total_input = sum(r.input_tokens for r in rows)
            total_output = sum(r.output_tokens for r in rows)
            total_cost = sum(r.cost_usd for r in rows)
            by_endpoint: dict[str, dict] = {}
            for r in rows:
                ep = by_endpoint.setdefault(r.endpoint, {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0})
                ep["input_tokens"] += r.input_tokens
                ep["output_tokens"] += r.output_tokens
                ep["cost_usd"] += r.cost_usd
                ep["calls"] += 1
            return {
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_cost_usd": round(total_cost, 6),
                "total_calls": len(rows),
                "by_endpoint": by_endpoint,
            }

    # --- Workspace-scoped house list ---

    def list_houses(self, workspace_id: str | None = None) -> list[MessageHouse]:
        with self.session() as s:
            q = s.query(HouseModel)
            if workspace_id and workspace_id != "all":
                q = q.filter(HouseModel.workspace_id == workspace_id)
            rows = q.all()
            return [_house_from_row(r) for r in rows]


def _house_from_row(row: HouseModel) -> MessageHouse:
    return MessageHouse(
        id=UUID(row.id),
        name=row.name,
        source=row.source,
        source_id=row.source_id,
        summary=row.summary,
        audience=row.audience,
        brand_personality=row.brand_personality,
        positioning=row.positioning,
        tagline=row.tagline,
        differentiation=row.differentiation,
        status=HouseStatus(row.status),
        last_synced=row.last_synced,
    )


def _msg_from_row(row: KeyMessageModel) -> KeyMessage:
    return KeyMessage(
        id=UUID(row.id),
        message_house_id=UUID(row.message_house_id),
        section_type=SectionType(row.section_type),
        priority=row.priority,
        content=row.content,
        variants=row.variants or {},
        personas=row.personas or [],
        channels=[Channel(c) for c in (row.channels or ["all"])],
        source_chunk_id=row.source_chunk_id,
    )


def _persona_from_row(row: PersonaModel) -> Persona:
    return Persona(
        id=UUID(row.id),
        message_house_id=UUID(row.message_house_id),
        name=row.name,
        description=row.description,
        pain_points=row.pain_points or [],
        buying_triggers=row.buying_triggers or [],
        objections=row.objections or [],
    )