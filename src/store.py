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
    Index,
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

from src.models import Channel, DocumentType, HouseStatus, KeyMessage, MessageHouse, Persona, SectionType

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


class ChannelModel(Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


_DEFAULT_CHANNELS = [
    ("all", "All Channels", "Universal — applies to all channels", True),
    ("email", "Email", "Email campaigns and newsletters", True),
    ("linkedin", "LinkedIn", "LinkedIn posts and sponsored content", True),
    ("twitter", "Twitter / X", "Twitter and X posts", True),
    ("paid_ads", "Paid Ads", "Display, search, and social advertising", True),
    ("landing_page", "Landing Page", "Website landing pages and hero copy", True),
    ("sales_deck", "Sales Deck", "Slide decks and pitch presentations", True),
]


class HouseModel(Base):
    __tablename__ = "message_houses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="default")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False, default="message_house", server_default="message_house")
    summary: Mapped[str] = mapped_column(Text, default="")
    audience: Mapped[str] = mapped_column(Text, default="")
    brand_personality: Mapped[str] = mapped_column(Text, default="")
    positioning: Mapped[str] = mapped_column(Text, default="")
    tagline: Mapped[str] = mapped_column(String(500), default="")
    differentiation: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    last_synced: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    key_messages: Mapped[list["KeyMessageModel"]] = relationship(
        back_populates="message_house", cascade="all, delete-orphan"
    )
    personas: Mapped[list["PersonaModel"]] = relationship(
        back_populates="message_house", cascade="all, delete-orphan"
    )
    pillars: Mapped[list["PillarModel"]] = relationship(
        back_populates="message_house", cascade="all, delete-orphan"
    )


class PillarModel(Base):
    __tablename__ = "pillars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    house_id: Mapped[str] = mapped_column(String(36), ForeignKey("message_houses.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="")
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    message_house: Mapped["HouseModel"] = relationship(back_populates="pillars")


class PainPointModel(Base):
    __tablename__ = "pain_points"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    persona_id: Mapped[str] = mapped_column(String(36), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class BuyingTriggerModel(Base):
    __tablename__ = "buying_triggers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    persona_id: Mapped[str] = mapped_column(String(36), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class ObjectionModel(Base):
    __tablename__ = "objections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    persona_id: Mapped[str] = mapped_column(String(36), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)


class KeyMessageModel(Base):
    __tablename__ = "key_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    message_house_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("message_houses.id"), nullable=False
    )
    pillar_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("pillars.id", ondelete="SET NULL"), nullable=True)
    section_type: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variants: Mapped[dict] = mapped_column(JSON, default=dict)
    personas: Mapped[list] = mapped_column(JSON, default=list)
    channels: Mapped[list] = mapped_column(JSON, default=["all"])
    source_chunk_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pain_point_ids: Mapped[list] = mapped_column(JSON, default=list)
    objection_ids: Mapped[list] = mapped_column(JSON, default=list)
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


# Performance indexes on high-cardinality FK / filter columns
Index("ix_km_house_id", KeyMessageModel.message_house_id)
Index("ix_km_pillar_id", KeyMessageModel.pillar_id)
Index("ix_persona_house_id", PersonaModel.message_house_id)
Index("ix_snapshot_house_id", SnapshotModel.house_id)
Index("ix_artifact_house_id", ArtifactHistoryModel.house_id)
Index("ix_token_usage_workspace", TokenUsageModel.workspace_id)
Index("ix_api_key_workspace", ApiKeyModel.workspace_id)
Index("ix_house_workspace", HouseModel.workspace_id)
Index("ix_pillar_house_id", PillarModel.house_id)


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
        self._migrate()
        self._ensure_default_workspace()
        self._seed_default_channels()

    def _migrate(self) -> None:
        """Apply additive migrations for columns added after initial schema creation."""
        from sqlalchemy import text, inspect
        insp = inspect(self.engine)
        with self.engine.connect() as conn:
            # Add document_type to message_houses if missing
            if "message_houses" in insp.get_table_names():
                cols = {c["name"] for c in insp.get_columns("message_houses")}
                if "document_type" not in cols:
                    conn.execute(text(
                        "ALTER TABLE message_houses ADD COLUMN document_type VARCHAR(30) "
                        "NOT NULL DEFAULT 'message_house'"
                    ))
                    conn.commit()

            # Create pillars table if not exists
            if "pillars" not in insp.get_table_names():
                conn.execute(text("""
                    CREATE TABLE pillars (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        house_id VARCHAR(36) NOT NULL REFERENCES message_houses(id) ON DELETE CASCADE,
                        name TEXT NOT NULL,
                        description TEXT,
                        display_order INTEGER DEFAULT 0
                    )
                """))
                conn.commit()

            # Add pillar_id column to key_messages if missing
            if "key_messages" in insp.get_table_names():
                km_cols = {c["name"] for c in insp.get_columns("key_messages")}
                if "pillar_id" not in km_cols:
                    try:
                        conn.execute(text("ALTER TABLE key_messages ADD COLUMN pillar_id INTEGER REFERENCES pillars(id) ON DELETE SET NULL"))
                        conn.commit()
                    except Exception:
                        pass  # Column already exists or other issue

            # Create pain_points table
            if "pain_points" not in insp.get_table_names():
                conn.execute(text("""
                    CREATE TABLE pain_points (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        persona_id TEXT NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
                        content TEXT NOT NULL
                    )
                """))
                conn.commit()

            # Create buying_triggers table
            if "buying_triggers" not in insp.get_table_names():
                conn.execute(text("""
                    CREATE TABLE buying_triggers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        persona_id TEXT NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
                        content TEXT NOT NULL
                    )
                """))
                conn.commit()

            # Create objections table
            if "objections" not in insp.get_table_names():
                conn.execute(text("""
                    CREATE TABLE objections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        persona_id TEXT NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
                        statement TEXT NOT NULL,
                        response TEXT
                    )
                """))
                conn.commit()

            # Add pain_point_ids and objection_ids to key_messages
            if "key_messages" in insp.get_table_names():
                km_cols = {c["name"] for c in insp.get_columns("key_messages")}
                for col in ("pain_point_ids", "objection_ids"):
                    if col not in km_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE key_messages ADD COLUMN {col} JSON DEFAULT '[]'"))
                            conn.commit()
                        except Exception:
                            pass

    def _seed_default_channels(self) -> None:
        with self.session() as s:
            for ch_id, name, description, is_default in _DEFAULT_CHANNELS:
                if not s.get(ChannelModel, ch_id):
                    s.add(ChannelModel(id=ch_id, name=name, description=description,
                                       is_default=is_default, created_at=_now()))
            s.commit()

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
        _invalidate_graph()

    def get_house(self, house_id: UUID) -> MessageHouse | None:
        with self.session() as s:
            row = s.get(HouseModel, str(house_id))
            if not row:
                return None
            return _house_from_row(row)

    def get_house_workspace_id(self, house_id: UUID) -> str | None:
        with self.session() as s:
            row = s.get(HouseModel, str(house_id))
            return row.workspace_id if row else None

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
        _invalidate_graph()

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
        _invalidate_graph()

    def get_personas(self, house_id: UUID) -> list[Persona]:
        with self.session() as s:
            rows = (
                s.query(PersonaModel)
                .filter(PersonaModel.message_house_id == str(house_id))
                .all()
            )
            return [_persona_from_row(r) for r in rows]

    def get_persona_by_name(self, house_id: UUID, name: str) -> Persona | None:
        with self.session() as s:
            row = (
                s.query(PersonaModel)
                .filter(PersonaModel.message_house_id == str(house_id), PersonaModel.name == name)
                .first()
            )
            return _persona_from_row(row) if row else None

    def bulk_create_pain_points(self, persona_id: str, items: list[str]) -> list[int]:
        with self.session() as s:
            new_ids = []
            for content in items:
                pp = PainPointModel(persona_id=persona_id, content=content)
                s.add(pp)
                s.flush()
                new_ids.append(pp.id)
            s.commit()
            return new_ids

    def bulk_create_buying_triggers(self, persona_id: str, items: list[str]) -> list[int]:
        with self.session() as s:
            new_ids = []
            for content in items:
                bt = BuyingTriggerModel(persona_id=persona_id, content=content)
                s.add(bt)
                s.flush()
                new_ids.append(bt.id)
            s.commit()
            return new_ids

    def bulk_create_objections(self, persona_id: str, items: list[dict]) -> list[int]:
        with self.session() as s:
            new_ids = []
            for ob in items:
                stmt = ob.get("statement", "")
                resp = ob.get("response")
                obj = ObjectionModel(persona_id=persona_id, statement=stmt, response=resp)
                s.add(obj)
                s.flush()
                new_ids.append(obj.id)
            s.commit()
            return new_ids

    def delete_persona_sub_attrs(self, persona_id: str) -> None:
        with self.session() as s:
            s.query(PainPointModel).filter(PainPointModel.persona_id == persona_id).delete()
            s.query(BuyingTriggerModel).filter(BuyingTriggerModel.persona_id == persona_id).delete()
            s.query(ObjectionModel).filter(ObjectionModel.persona_id == persona_id).delete()
            s.commit()

    def update_chunk_links(self, chunk_id: str, pain_point_ids: list[int], objection_ids: list[int]) -> None:
        with self.session() as s:
            row = s.get(KeyMessageModel, chunk_id)
            if row:
                row.pain_point_ids = pain_point_ids
                row.objection_ids = objection_ids
                s.commit()

    def list_pain_points(self, persona_id: str) -> list:
        with self.session() as s:
            return s.query(PainPointModel).filter(PainPointModel.persona_id == persona_id).all()

    def list_objections(self, persona_id: str) -> list:
        with self.session() as s:
            return s.query(ObjectionModel).filter(ObjectionModel.persona_id == persona_id).all()

    def list_buying_triggers(self, persona_id: str) -> list:
        with self.session() as s:
            return s.query(BuyingTriggerModel).filter(BuyingTriggerModel.persona_id == persona_id).all()

    def delete_house(self, house_id: UUID) -> bool:
        with self.session() as s:
            row = s.get(HouseModel, str(house_id))
            if row:
                s.delete(row)
                s.commit()
                _invalidate_graph()
                return True
            return False

    def delete_key_message(self, msg_id: UUID) -> bool:
        with self.session() as s:
            row = s.get(KeyMessageModel, str(msg_id))
            if row:
                s.delete(row)
                s.commit()
                _invalidate_graph()
                return True
            return False

    def delete_persona(self, persona_id: UUID) -> bool:
        with self.session() as s:
            row = s.get(PersonaModel, str(persona_id))
            if row:
                s.delete(row)
                s.commit()
                _invalidate_graph()
                return True
            return False

    # --- Pillars ---

    def create_pillar(self, house_id: UUID, name: str, description: str | None = None, display_order: int = 0) -> int:
        """Insert a new pillar, return its id."""
        with self.session() as s:
            row = PillarModel(
                house_id=str(house_id),
                name=name,
                description=description or "",
                display_order=display_order,
            )
            s.add(row)
            s.commit()
            return row.id
        _invalidate_graph()

    def list_pillars(self, house_id: UUID) -> list["Pillar"]:
        """Return all pillars for a house ordered by display_order."""
        with self.session() as s:
            rows = (
                s.query(PillarModel)
                .filter(PillarModel.house_id == str(house_id))
                .order_by(PillarModel.display_order, PillarModel.name)
                .all()
            )
            return [_pillar_from_row(r) for r in rows]

    def update_pillar(self, pillar_id: int, **kwargs) -> bool:
        """Partial update. Returns True if row was found."""
        with self.session() as s:
            row = s.get(PillarModel, pillar_id)
            if not row:
                return False
            for k, v in kwargs.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            s.commit()
            _invalidate_graph()
            return True

    def delete_pillar(self, pillar_id: int) -> bool:
        """Delete pillar; SET NULL cascades to key_messages. Returns True if found."""
        with self.session() as s:
            row = s.get(PillarModel, pillar_id)
            if not row:
                return False
            s.delete(row)
            s.commit()
            _invalidate_graph()
            return True

    def assign_chunk_to_pillar(self, chunk_id: UUID, pillar_id: int | None) -> bool:
        """Set key_messages.pillar_id. Pass None to unassign."""
        with self.session() as s:
            row = s.get(KeyMessageModel, str(chunk_id))
            if not row:
                return False
            row.pillar_id = pillar_id
            s.commit()
            _invalidate_graph()
            return True

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

    def diff_snapshot(self, snapshot_id: UUID) -> dict:
        """Compare a snapshot against the current state of its house."""
        snap = self.get_snapshot(snapshot_id)
        if not snap:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        snap_data = snap["snapshot_json"]
        house_id = UUID(snap_data["house"]["id"])

        current_house = self.get_house(house_id)
        if not current_house:
            raise ValueError("House no longer exists")

        current_messages = self.get_key_messages(house_id)
        current_personas = self.get_personas(house_id)

        field_changes = {}
        snap_house = snap_data["house"]
        for field in ("name", "summary", "audience", "brand_personality", "positioning", "tagline", "differentiation"):
            snap_val = snap_house.get(field, "")
            curr_val = getattr(current_house, field, "") or ""
            if snap_val != curr_val:
                field_changes[field] = {"snapshot": snap_val, "current": curr_val}

        snap_msgs = {m["id"]: m for m in snap_data.get("messages", [])}
        curr_msgs = {str(m.id): m for m in current_messages}

        added_messages = [
            {"id": mid, "content": m.content, "section_type": str(m.section_type)}
            for mid, m in curr_msgs.items() if mid not in snap_msgs
        ]
        removed_messages = [
            {"id": mid, "content": m["content"], "section_type": m["section_type"]}
            for mid, m in snap_msgs.items() if mid not in curr_msgs
        ]
        changed_messages = []
        for mid in snap_msgs:
            if mid in curr_msgs:
                snap_m = snap_msgs[mid]
                curr_m = curr_msgs[mid]
                if snap_m["content"] != curr_m.content:
                    changed_messages.append({
                        "id": mid,
                        "snapshot_content": snap_m["content"],
                        "current_content": curr_m.content,
                        "section_type": str(curr_m.section_type),
                    })

        snap_personas = {p["id"]: p for p in snap_data.get("personas", [])}
        curr_personas = {str(p.id): p for p in current_personas}
        added_personas = [{"id": pid, "name": p.name} for pid, p in curr_personas.items() if pid not in snap_personas]
        removed_personas = [{"id": pid, "name": p["name"]} for pid, p in snap_personas.items() if pid not in curr_personas]

        return {
            "snapshot_id": str(snapshot_id),
            "snapshot_label": snap["label"],
            "snapshot_created_at": snap["created_at"],
            "house_id": str(house_id),
            "field_changes": field_changes,
            "messages": {
                "added": added_messages,
                "removed": removed_messages,
                "changed": changed_messages,
            },
            "personas": {
                "added": added_personas,
                "removed": removed_personas,
            },
            "has_changes": bool(field_changes or added_messages or removed_messages or changed_messages or added_personas or removed_personas),
        }

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

    def list_recent_artifacts(self, limit: int = 5) -> list[dict]:
        with self.session() as s:
            rows = (
                s.query(ArtifactHistoryModel)
                .order_by(ArtifactHistoryModel.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "house_id": r.house_id,
                    "skill_id": r.skill_id,
                    "house_name": r.house_name,
                    "created_at": r.created_at.isoformat(),
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

    # --- Channels ---

    def get_channels(self) -> list[dict]:
        with self.session() as s:
            rows = s.query(ChannelModel).order_by(ChannelModel.is_default.desc(), ChannelModel.name).all()
            return [{"id": r.id, "name": r.name, "description": r.description,
                     "is_default": r.is_default, "created_at": r.created_at.isoformat()} for r in rows]

    def upsert_channel(self, ch_id: str, name: str, description: str = "") -> dict:
        with self.session() as s:
            existing = s.get(ChannelModel, ch_id)
            if existing:
                existing.name = name
                existing.description = description
            else:
                s.add(ChannelModel(id=ch_id, name=name, description=description,
                                   is_default=False, created_at=_now()))
            s.commit()
            row = s.get(ChannelModel, ch_id)
            return {"id": row.id, "name": row.name, "description": row.description,
                    "is_default": row.is_default, "created_at": row.created_at.isoformat()}

    def delete_channel(self, ch_id: str) -> bool:
        with self.session() as s:
            row = s.get(ChannelModel, ch_id)
            if not row:
                return False
            if row.is_default:
                raise ValueError("Cannot delete a default channel")
            s.delete(row)
            s.commit()
            return True

    # --- Workspace-scoped house list ---

    def list_houses(self, workspace_id: str | None = None) -> list[MessageHouse]:
        with self.session() as s:
            q = s.query(HouseModel)
            if workspace_id and workspace_id != "all":
                q = q.filter(HouseModel.workspace_id == workspace_id)
            rows = q.all()
            return [_house_from_row(r) for r in rows]

    def list_houses_with_counts(self, workspace_id: str | None = None) -> list[dict]:
        """Return houses with pre-aggregated message/persona counts — avoids N+1."""
        from sqlalchemy import func
        with self.session() as s:
            msg_counts = (
                s.query(KeyMessageModel.message_house_id, func.count().label("cnt"))
                .group_by(KeyMessageModel.message_house_id)
                .subquery()
            )
            persona_counts = (
                s.query(PersonaModel.message_house_id, func.count().label("cnt"))
                .group_by(PersonaModel.message_house_id)
                .subquery()
            )
            q = (
                s.query(
                    HouseModel,
                    func.coalesce(msg_counts.c.cnt, 0).label("message_count"),
                    func.coalesce(persona_counts.c.cnt, 0).label("persona_count"),
                )
                .outerjoin(msg_counts, HouseModel.id == msg_counts.c.message_house_id)
                .outerjoin(persona_counts, HouseModel.id == persona_counts.c.message_house_id)
            )
            if workspace_id and workspace_id != "all":
                q = q.filter(HouseModel.workspace_id == workspace_id)
            return [
                {
                    "house": _house_from_row(row),
                    "message_count": int(mc),
                    "persona_count": int(pc),
                }
                for row, mc, pc in q.all()
            ]


def _safe_section_type(value: str) -> SectionType:
    try:
        return SectionType(value)
    except ValueError:
        return SectionType.POSITIONING


def _safe_channel(value: str) -> Channel:
    try:
        return Channel(value)
    except ValueError:
        return Channel.ALL


def _invalidate_graph() -> None:
    """Notify the graph engine that its derived state is stale."""
    try:
        from src.grounding.graph import get_graph_engine
        get_graph_engine()._built = False
    except Exception:
        pass


def _house_from_row(row: HouseModel) -> MessageHouse:
    from src.models import DocumentType
    return MessageHouse(
        id=UUID(row.id),
        name=row.name,
        source=row.source,
        source_id=row.source_id,
        document_type=row.document_type if row.document_type else "message_house",
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
        pillar_id=row.pillar_id,
        section_type=_safe_section_type(row.section_type),
        priority=row.priority,
        content=row.content,
        variants=row.variants or {},
        personas=row.personas or [],
        channels=[_safe_channel(c) for c in (row.channels or ["all"])],
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


def _pillar_from_row(row: PillarModel) -> "Pillar":
    from src.models import Pillar
    return Pillar(
        id=row.id,
        house_id=row.house_id,
        name=row.name,
        description=row.description,
        display_order=row.display_order,
    )