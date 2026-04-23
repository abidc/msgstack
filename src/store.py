"""SQLite-backed message house storage."""

from datetime import datetime
from pathlib import Path
from typing import Self
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
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
                for k, v in house.model_dump().items():
                    setattr(existing, k, v)
            else:
                s.add(HouseModel(**house.model_dump()))
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
                for k, v in msg.model_dump().items():
                    setattr(existing, k, v)
            else:
                s.add(KeyMessageModel(**msg.model_dump()))
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
                for k, v in persona.model_dump().items():
                    setattr(existing, k, v)
            else:
                s.add(PersonaModel(**persona.model_dump()))
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