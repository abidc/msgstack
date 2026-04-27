"""SQLite-backed message house storage."""

from datetime import datetime
from pathlib import Path
from typing import Self
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
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


def _to_db(data: dict) -> dict:
    return {k: str(v) if isinstance(v, UUID) else v for k, v in data.items()}


class Base(DeclarativeBase):
    pass


class HouseModel(Base):
    __tablename__ = "message_houses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
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
    def __init__(self, db_path: str | Path = "msgstack.db"):
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.session_factory = sessionmaker(bind=self.engine)

    def init(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self.session_factory()

    def upsert_house(self, house: MessageHouse) -> None:
        with self.session() as s:
            existing = s.get(HouseModel, str(house.id))
            if existing:
                for k, v in _to_db(house.model_dump()).items():
                    if k != "id":
                        setattr(existing, k, v)
            else:
                s.add(HouseModel(**_to_db(house.model_dump())))
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

    def list_houses(self) -> list[MessageHouse]:
        with self.session() as s:
            rows = s.query(HouseModel).all()
            return [_house_from_row(r) for r in rows]

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
        now = datetime.utcnow()
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
        now = datetime.utcnow()
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