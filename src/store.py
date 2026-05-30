"""SQLite / PostgreSQL-backed canon storage."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Self
from uuid import UUID, uuid4
import uuid as _uuid

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
    Table,
    Column,
    PrimaryKeyConstraint,
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

from src.models import (
    BrandSettings, Channel, DocumentType, DomainStatus, EntryStatus,
    CanonDomain, CanonEntry, Persona, SectionType,
    HouseStatus, KeyMessage, MessageHouse  # Deprecated aliases
)


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
    penpot_project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
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
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


_DEFAULT_CHANNELS = [
    ("all", "All Channels", "Universal — applies to all channels", False),
    ("email", "Email", "Email campaigns and newsletters", False),
    ("linkedin", "LinkedIn", "LinkedIn posts and sponsored content", False),
    ("twitter", "Twitter / X", "Twitter and X posts", False),
    ("paid_ads", "Paid Ads", "Display, search, and social advertising", False),
    ("landing_page", "Landing Page", "Website landing pages and hero copy", False),
    ("sales_deck", "Sales Deck", "Slide decks and pitch presentations", False),
]

# Association table for CanonEntryModel and ChannelModel (many-to-many)
canon_entry_channel_association = Table(
    "canon_entry_channel_association",
    Base.metadata,
    Column("canon_entry_id", String(36), ForeignKey("canon_entries.id", ondelete="CASCADE")),
    Column("channel_id", String(50), ForeignKey("channels.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("canon_entry_id", "channel_id")
)

# Alias for backward compatibility
key_message_channel_association = canon_entry_channel_association


class CanonDomainModel(Base):
    __tablename__ = "canon_domains"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="default")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False, default="canon_domain", server_default="canon_domain")
    summary: Mapped[str] = mapped_column(Text, default="")
    audience: Mapped[str] = mapped_column(Text, default="")
    brand_personality: Mapped[str] = mapped_column(Text, default="")
    positioning: Mapped[str] = mapped_column(Text, default="")
    tagline: Mapped[str] = mapped_column(String(500), default="")
    differentiation: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    last_synced: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_reviewed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    canon_entries: Mapped[list["CanonEntryModel"]] = relationship(
        back_populates="canon_domain", cascade="all, delete-orphan"
    )
    personas: Mapped[list["PersonaModel"]] = relationship(
        back_populates="canon_domain", cascade="all, delete-orphan"
    )
    pillars: Mapped[list["PillarModel"]] = relationship(
        back_populates="canon_domain", cascade="all, delete-orphan"
    )


HouseModel = CanonDomainModel  # Deprecated alias


class PillarModel(Base):
    __tablename__ = "pillars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canon_domain_id: Mapped[str] = mapped_column(String(36), ForeignKey("canon_domains.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="")
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    canon_domain: Mapped["CanonDomainModel"] = relationship(back_populates="pillars")

    # Property alias for compatibility
    @property
    def house_id(self) -> str:
        return self.canon_domain_id
    @house_id.setter
    def house_id(self, val: str) -> None:
        self.canon_domain_id = val

    @property
    def message_house(self) -> "CanonDomainModel":
        return self.canon_domain
    @message_house.setter
    def message_house(self, val: "CanonDomainModel") -> None:
        self.canon_domain = val


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


class CanonEntryModel(Base):
    __tablename__ = "canon_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    canon_domain_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("canon_domains.id"), nullable=False
    )
    pillar_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("pillars.id", ondelete="SET NULL"), nullable=True)
    section_type: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    variants: Mapped[dict] = mapped_column(JSON, default=dict)
    personas: Mapped[list] = mapped_column(JSON, default=list)
    # Many-to-many relationship with ChannelModel
    channels: Mapped[list["ChannelModel"]] = relationship(
        secondary=canon_entry_channel_association,
        backref="canon_entries"
    )
    source_chunk_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canon_domain: Mapped["CanonDomainModel"] = relationship(back_populates="canon_entries")

    @property
    def message_house_id(self) -> str:
        return self.canon_domain_id
    @message_house_id.setter
    def message_house_id(self, val: str) -> None:
        self.canon_domain_id = val

    @property
    def message_house(self) -> "CanonDomainModel":
        return self.canon_domain
    @message_house.setter
    def message_house(self, val: "CanonDomainModel") -> None:
        self.canon_domain = val


KeyMessageModel = CanonEntryModel  # Deprecated alias


class PersonaModel(Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    canon_domain_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("canon_domains.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="")
    pain_points: Mapped[list] = mapped_column(JSON, default=list)
    buying_triggers: Mapped[list] = mapped_column(JSON, default=list)
    objections: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    canon_domain: Mapped["CanonDomainModel"] = relationship(back_populates="personas")

    @property
    def message_house_id(self) -> str:
        return self.canon_domain_id
    @message_house_id.setter
    def message_house_id(self, val: str) -> None:
        self.canon_domain_id = val

    @property
    def message_house(self) -> "CanonDomainModel":
        return self.canon_domain
    @message_house.setter
    def message_house(self, val: "CanonDomainModel") -> None:
        self.canon_domain = val


class SnapshotModel(Base):
    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    canon_domain_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("canon_domains.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), default="")
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    @property
    def house_id(self) -> str:
        return self.canon_domain_id
    @house_id.setter
    def house_id(self, val: str) -> None:
        self.canon_domain_id = val


class ArtifactHistoryModel(Base):
    __tablename__ = "artifact_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    canon_domain_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("canon_domains.id"), nullable=False
    )
    skill_id: Mapped[str] = mapped_column(String(100), nullable=False)
    house_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sections_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    alignment_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    @property
    def house_id(self) -> str:
        return self.canon_domain_id
    @house_id.setter
    def house_id(self, val: str) -> None:
        self.canon_domain_id = val


class ArtifactRatingModel(Base):
    __tablename__ = "artifact_ratings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("artifact_history.id"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    tag: Mapped[str] = mapped_column(String(20), default="good")  # "good" or "bad"
    rated_by: Mapped[str] = mapped_column(String(255), default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class ChunkUsageStatModel(Base):
    __tablename__ = "chunk_usage_stats"

    chunk_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    avg_rating: Mapped[float] = mapped_column(Float, default=0.0)
    boost_factor: Mapped[float] = mapped_column(Float, default=1.0)


class SourceConnectionModel(Base):
    __tablename__ = "source_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="default")
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # "google_drive"
    account_email: Mapped[str] = mapped_column(String(255), default="")
    folder_id: Mapped[str] = mapped_column(String(255), nullable=False)
    folder_name: Mapped[str] = mapped_column(String(500), default="")
    access_token: Mapped[str] = mapped_column(Text, default="")
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    page_token: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(30), default="connected")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    source_files: Mapped[list["SourceFileModel"]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )


class SourceFileModel(Base):
    __tablename__ = "source_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    connection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_connections.id", ondelete="CASCADE"), nullable=False
    )
    drive_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), default="")
    canon_domain_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    drive_modified_at: Mapped[str] = mapped_column(String(50), default="")
    sync_status: Mapped[str] = mapped_column(String(30), default="pending")
    error_message: Mapped[str] = mapped_column(Text, default="")
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    connection: Mapped["SourceConnectionModel"] = relationship(back_populates="source_files")

    @property
    def house_id(self) -> str | None:
        return self.canon_domain_id
    @house_id.setter
    def house_id(self, val: str | None) -> None:
        self.canon_domain_id = val


class BrandSettingsModel(Base):
    __tablename__ = "brand_settings"

    workspace_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    primary_color: Mapped[str] = mapped_column(String(20), default="#1e293b")
    secondary_color: Mapped[str] = mapped_column(String(20), default="#3b82f6")
    accent_color: Mapped[str] = mapped_column(String(20), default="#f59e0b")
    background_color: Mapped[str] = mapped_column(String(20), default="#ffffff")
    text_color: Mapped[str] = mapped_column(String(20), default="#1e293b")
    font_heading: Mapped[str] = mapped_column(String(100), default="Inter")
    font_body: Mapped[str] = mapped_column(String(100), default="Inter")
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)


class BrandAssetModel(Base):
    __tablename__ = "brand_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    asset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "logo", "icon", "image"
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ReviewLogModel(Base):
    __tablename__ = "review_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    canon_domain_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("canon_domains.id", ondelete="CASCADE"), nullable=False
    )
    canon_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    performed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")

    @property
    def house_id(self) -> str:
        return self.canon_domain_id
    @house_id.setter
    def house_id(self, val: str) -> None:
        self.canon_domain_id = val

    @property
    def message_id(self) -> str | None:
        return self.canon_entry_id
    @message_id.setter
    def message_id(self, val: str | None) -> None:
        self.canon_entry_id = val


class VectorMetadataModel(Base):
    __tablename__ = "vector_metadata"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # e.g., 'chunk-UUID', 'field-UUID-field', 'kym-UUID'
    canon_domain_id: Mapped[str] = mapped_column(String(36), nullable=False)
    canon_domain_name: Mapped[str] = mapped_column(String(255), nullable=False)
    canon_domain_summary: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section_type: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    persona: Mapped[str] = mapped_column(String(255), default="general")
    channel: Mapped[str] = mapped_column(String(255), default="all")
    canon_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_synced: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def message_house_id(self) -> str:
        return self.canon_domain_id
    @message_house_id.setter
    def message_house_id(self, val: str) -> None:
        self.canon_domain_id = val

    @property
    def house_name(self) -> str:
        return self.canon_domain_name
    @house_name.setter
    def house_name(self, val: str) -> None:
        self.canon_domain_name = val

    @property
    def house_summary(self) -> str:
        return self.canon_domain_summary
    @house_summary.setter
    def house_summary(self, val: str) -> None:
        self.canon_domain_summary = val

    @property
    def key_message_id(self) -> str | None:
        return self.canon_entry_id
    @key_message_id.setter
    def key_message_id(self, val: str | None) -> None:
        self.canon_entry_id = val


# Performance indexes on high-cardinality FK / filter columns
Index("ix_km_house_id", CanonEntryModel.canon_domain_id)
Index("ix_km_pillar_id", CanonEntryModel.pillar_id)
Index("ix_persona_house_id", PersonaModel.canon_domain_id)
Index("ix_snapshot_house_id", SnapshotModel.canon_domain_id)
Index("ix_artifact_house_id", ArtifactHistoryModel.canon_domain_id)
Index("ix_token_usage_workspace", TokenUsageModel.workspace_id)
Index("ix_api_key_workspace", ApiKeyModel.workspace_id)
Index("ix_house_workspace", CanonDomainModel.workspace_id)
Index("ix_pillar_house_id", PillarModel.canon_domain_id)
Index("ix_source_files_conn", SourceFileModel.connection_id)
Index("ix_source_files_drive_id", SourceFileModel.drive_file_id)
Index("ix_review_logs_house_id", ReviewLogModel.canon_domain_id)
Index("ix_review_logs_timestamp", ReviewLogModel.timestamp)
Index("ix_artifact_rating_artifact_id", ArtifactRatingModel.artifact_id)
Index("ix_chunk_usage_chunk_id", ChunkUsageStatModel.chunk_id)
Index("ix_vector_metadata_house_id", VectorMetadataModel.canon_domain_id)


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
        self._migrate()
        Base.metadata.create_all(self.engine)
        self._ensure_default_workspace()
        self._seed_default_channels()

    def _migrate(self) -> None:
        """Apply table renames, column renames, and additive migrations for columns."""
        from sqlalchemy import text, inspect
        insp = inspect(self.engine)
        tables = insp.get_table_names()
        with self.engine.connect() as conn:
            # 1. Table renames
            if "message_houses" in tables and "canon_domains" not in tables:
                conn.execute(text("ALTER TABLE message_houses RENAME TO canon_domains"))
                conn.commit()
            if "key_messages" in tables and "canon_entries" not in tables:
                conn.execute(text("ALTER TABLE key_messages RENAME TO canon_entries"))
                conn.commit()
            if "key_message_channel_association" in tables and "canon_entry_channel_association" not in tables:
                conn.execute(text("ALTER TABLE key_message_channel_association RENAME TO canon_entry_channel_association"))
                conn.commit()

            # Refresh inspector to reflect table renames
            insp = inspect(self.engine)
            tables = insp.get_table_names()

            # 2. Column renames
            if "canon_entries" in tables:
                cols = {c["name"] for c in insp.get_columns("canon_entries")}
                if "message_house_id" in cols and "canon_domain_id" not in cols:
                    conn.execute(text("ALTER TABLE canon_entries RENAME COLUMN message_house_id TO canon_domain_id"))
                    conn.commit()
            if "personas" in tables:
                cols = {c["name"] for c in insp.get_columns("personas")}
                if "message_house_id" in cols and "canon_domain_id" not in cols:
                    conn.execute(text("ALTER TABLE personas RENAME COLUMN message_house_id TO canon_domain_id"))
                    conn.commit()
            if "pillars" in tables:
                cols = {c["name"] for c in insp.get_columns("pillars")}
                if "house_id" in cols and "canon_domain_id" not in cols:
                    conn.execute(text("ALTER TABLE pillars RENAME COLUMN house_id TO canon_domain_id"))
                    conn.commit()
            if "snapshots" in tables:
                cols = {c["name"] for c in insp.get_columns("snapshots")}
                if "house_id" in cols and "canon_domain_id" not in cols:
                    conn.execute(text("ALTER TABLE snapshots RENAME COLUMN house_id TO canon_domain_id"))
                    conn.commit()
            if "artifact_history" in tables:
                cols = {c["name"] for c in insp.get_columns("artifact_history")}
                if "house_id" in cols and "canon_domain_id" not in cols:
                    conn.execute(text("ALTER TABLE artifact_history RENAME COLUMN house_id TO canon_domain_id"))
                    conn.commit()
            if "review_logs" in tables:
                cols = {c["name"] for c in insp.get_columns("review_logs")}
                if "house_id" in cols and "canon_domain_id" not in cols:
                    conn.execute(text("ALTER TABLE review_logs RENAME COLUMN house_id TO canon_domain_id"))
                    conn.commit()
                if "message_id" in cols and "canon_entry_id" not in cols:
                    conn.execute(text("ALTER TABLE review_logs RENAME COLUMN message_id TO canon_entry_id"))
                    conn.commit()
            if "vector_metadata" in tables:
                cols = {c["name"] for c in insp.get_columns("vector_metadata")}
                if "message_house_id" in cols and "canon_domain_id" not in cols:
                    conn.execute(text("ALTER TABLE vector_metadata RENAME COLUMN message_house_id TO canon_domain_id"))
                    conn.commit()
                if "key_message_id" in cols and "canon_entry_id" not in cols:
                    conn.execute(text("ALTER TABLE vector_metadata RENAME COLUMN key_message_id TO canon_entry_id"))
                    conn.commit()
                if "house_name" in cols and "canon_domain_name" not in cols:
                    conn.execute(text("ALTER TABLE vector_metadata RENAME COLUMN house_name TO canon_domain_name"))
                    conn.commit()
                if "house_summary" in cols and "canon_domain_summary" not in cols:
                    conn.execute(text("ALTER TABLE vector_metadata RENAME COLUMN house_summary TO canon_domain_summary"))
                    conn.commit()
            if "canon_entry_channel_association" in tables:
                cols = {c["name"] for c in insp.get_columns("canon_entry_channel_association")}
                if "key_message_id" in cols and "canon_entry_id" not in cols:
                    conn.execute(text("ALTER TABLE canon_entry_channel_association RENAME COLUMN key_message_id TO canon_entry_id"))
                    conn.commit()
            if "source_files" in tables:
                cols = {c["name"] for c in insp.get_columns("source_files")}
                if "house_id" in cols and "canon_domain_id" not in cols:
                    conn.execute(text("ALTER TABLE source_files RENAME COLUMN house_id TO canon_domain_id"))
                    conn.commit()

            # 3. Additive migrations
            if "canon_domains" in tables:
                mh_cols = {c["name"] for c in insp.get_columns("canon_domains")}
                if "document_type" not in mh_cols:
                    conn.execute(text(
                        "ALTER TABLE canon_domains ADD COLUMN document_type VARCHAR(30) "
                        "NOT NULL DEFAULT 'canon_domain'"
                    ))
                    conn.commit()
                if "last_reviewed" not in mh_cols:
                    try:
                        conn.execute(text("ALTER TABLE canon_domains ADD COLUMN last_reviewed DATETIME"))
                        conn.commit()
                    except Exception:
                        pass

            if "workspaces" in tables:
                ws_cols = {c["name"] for c in insp.get_columns("workspaces")}
                if "penpot_project_id" not in ws_cols:
                    try:
                        conn.execute(text("ALTER TABLE workspaces ADD COLUMN penpot_project_id TEXT"))
                        conn.commit()
                    except Exception:
                        pass

            if "pillars" not in tables:
                conn.execute(text("""
                    CREATE TABLE pillars (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        canon_domain_id VARCHAR(36) NOT NULL REFERENCES canon_domains(id) ON DELETE CASCADE,
                        name TEXT NOT NULL,
                        description TEXT,
                        display_order INTEGER DEFAULT 0
                    )
                """))
                conn.commit()

            if "canon_entries" in tables:
                km_cols = {c["name"] for c in insp.get_columns("canon_entries")}
                if "pillar_id" not in km_cols:
                    try:
                        conn.execute(text("ALTER TABLE canon_entries ADD COLUMN pillar_id INTEGER REFERENCES pillars(id) ON DELETE SET NULL"))
                        conn.commit()
                    except Exception:
                        pass
                for col, col_def in (
                    ("status", "VARCHAR(20) DEFAULT 'draft'"),
                    ("approved_by", "VARCHAR(255)"),
                    ("approved_at", "DATETIME"),
                ):
                    if col not in km_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE canon_entries ADD COLUMN {col} {col_def}"))
                            conn.commit()
                        except Exception:
                            pass

            if "pain_points" not in tables:
                conn.execute(text("""
                    CREATE TABLE pain_points (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        persona_id TEXT NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
                        content TEXT NOT NULL
                    )
                """))
                conn.commit()

            if "buying_triggers" not in tables:
                conn.execute(text("""
                    CREATE TABLE buying_triggers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        persona_id TEXT NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
                        content TEXT NOT NULL
                    )
                """))
                conn.commit()

            if "objections" not in tables:
                conn.execute(text("""
                    CREATE TABLE objections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        persona_id TEXT NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
                        statement TEXT NOT NULL,
                        response TEXT
                    )
                """))
                conn.commit()

            if "review_logs" not in tables:
                conn.execute(text("""
                    CREATE TABLE review_logs (
                        id TEXT PRIMARY KEY,
                        canon_domain_id TEXT NOT NULL REFERENCES canon_domains(id) ON DELETE CASCADE,
                        canon_entry_id TEXT,
                        action TEXT NOT NULL,
                        performed_by TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        notes TEXT DEFAULT ''
                    )
                """))
                conn.commit()

            if "artifact_history" in tables:
                ah_cols = {c["name"] for c in insp.get_columns("artifact_history")}
                if "status" not in ah_cols:
                    try:
                        conn.execute(text("ALTER TABLE artifact_history ADD COLUMN status VARCHAR(20) DEFAULT 'draft'"))
                        conn.commit()
                    except Exception:
                        pass
                if "alignment_score" not in ah_cols:
                    try:
                        conn.execute(text("ALTER TABLE artifact_history ADD COLUMN alignment_score INTEGER"))
                        conn.commit()
                    except Exception:
                        pass

            if "source_connections" not in tables:
                conn.execute(text("""
                    CREATE TABLE source_connections (
                        id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL DEFAULT 'default',
                        provider TEXT NOT NULL,
                        account_email TEXT DEFAULT '',
                        folder_id TEXT NOT NULL,
                        folder_name TEXT DEFAULT '',
                        access_token TEXT DEFAULT '',
                        refresh_token TEXT DEFAULT '',
                        page_token TEXT DEFAULT '',
                        status TEXT DEFAULT 'connected',
                        last_sync_at DATETIME,
                        error_message TEXT DEFAULT '',
                        created_at DATETIME NOT NULL
                    )
                """))
                conn.commit()

            if "source_files" not in tables:
                conn.execute(text("""
                    CREATE TABLE source_files (
                        id TEXT PRIMARY KEY,
                        connection_id TEXT NOT NULL REFERENCES source_connections(id) ON DELETE CASCADE,
                        drive_file_id TEXT NOT NULL,
                        file_name TEXT NOT NULL,
                        mime_type TEXT DEFAULT '',
                        canon_domain_id TEXT,
                        drive_modified_at TEXT DEFAULT '',
                        sync_status TEXT DEFAULT 'pending',
                        error_message TEXT DEFAULT '',
                        synced_at DATETIME
                    )
                """))
                conn.commit()

            if "brand_settings" not in tables:
                conn.execute(text("""
                    CREATE TABLE brand_settings (
                        workspace_id TEXT PRIMARY KEY,
                        primary_color TEXT DEFAULT '#1e293b',
                        secondary_color TEXT DEFAULT '#3b82f6',
                        accent_color TEXT DEFAULT '#f59e0b',
                        background_color TEXT DEFAULT '#ffffff',
                        text_color TEXT DEFAULT '#1e293b',
                        font_heading TEXT DEFAULT 'Inter',
                        font_body TEXT DEFAULT 'Inter',
                        logo_path TEXT
                    )
                 """))
                conn.commit()

            if "brand_assets" not in tables:
                conn.execute(text("""
                    CREATE TABLE brand_assets (
                        id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        asset_name TEXT NOT NULL,
                        asset_type TEXT DEFAULT 'logo',
                        file_path TEXT NOT NULL,
                        created_at DATETIME NOT NULL
                    )
                """))
                conn.commit()

            if "personas" in tables:
                p_cols = {c["name"] for c in insp.get_columns("personas")}
                for col, col_def in (
                    ("status", "VARCHAR(20) DEFAULT 'draft'"),
                    ("approved_by", "VARCHAR(255)"),
                    ("approved_at", "DATETIME"),
                ):
                    if col not in p_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE personas ADD COLUMN {col} {col_def}"))
                            conn.commit()
                        except Exception:
                            pass

    def _seed_default_channels(self) -> None:
        with self.session() as s:
            for ch_id, name, description, is_custom in _DEFAULT_CHANNELS:
                if not s.get(ChannelModel, ch_id):
                    s.add(ChannelModel(id=ch_id, name=name, description=description,
                                       is_custom=is_custom, created_at=_now()))
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

    def upsert_vector_metadata(
        self,
        id: str,
        message_house_id: UUID,
        house_name: str,
        house_summary: str,
        content: str,
        section_type: str,
        priority: int,
        persona: str,
        channel: str,
        key_message_id: Optional[UUID] = None,
        last_synced: Optional[datetime] = None,
        # Allow new naming parameters for compatibility
        canon_domain_id: Optional[UUID] = None,
        canon_domain_name: Optional[str] = None,
        canon_domain_summary: Optional[str] = None,
        canon_entry_id: Optional[UUID] = None,
    ) -> None:
        actual_domain_id = canon_domain_id or message_house_id
        actual_domain_name = canon_domain_name or house_name
        actual_domain_summary = canon_domain_summary or house_summary
        actual_entry_id = canon_entry_id or key_message_id

        with self.session() as s:
            existing = s.get(VectorMetadataModel, id)
            data = {
                "id": id,
                "canon_domain_id": str(actual_domain_id),
                "canon_domain_name": actual_domain_name,
                "canon_domain_summary": actual_domain_summary,
                "content": content,
                "section_type": section_type,
                "priority": priority,
                "persona": persona,
                "channel": channel,
                "canon_entry_id": str(actual_entry_id) if actual_entry_id else None,
                "last_synced": last_synced,
            }
            if existing:
                for k, v in data.items():
                    if k != "id":
                        setattr(existing, k, v)
            else:
                s.add(VectorMetadataModel(**data))
            s.commit()

    def delete_vector_metadata(self, id: str) -> None:
        with self.session() as s:
            existing = s.get(VectorMetadataModel, id)
            if existing:
                s.delete(existing)
                s.commit()

    def delete_vector_metadata_for_house(self, house_id: UUID) -> int:
        with self.session() as s:
            deleted = s.query(VectorMetadataModel).filter(
                VectorMetadataModel.canon_domain_id == str(house_id)
            ).delete()
            s.commit()
            return deleted

    def list_vector_metadata_matching_filters(
        self,
        message_houses: Optional[list[str]] = None,
        section_types: Optional[list[str]] = None,
        personas: Optional[list[str]] = None,
        channels: Optional[list[str]] = None,
        min_priority: Optional[int] = None,
        # compatibility argument names
        canon_domains: Optional[list[str]] = None,
    ) -> list[VectorMetadataModel]:
        actual_domains = canon_domains or message_houses
        with self.session() as s:
            query = s.query(VectorMetadataModel)
            if actual_domains:
                query = query.filter(VectorMetadataModel.canon_domain_id.in_(actual_domains))
            if section_types:
                query = query.filter(VectorMetadataModel.section_type.in_(section_types))
            if personas:
                query = query.filter(VectorMetadataModel.persona.in_(personas))
            if channels:
                query = query.filter(VectorMetadataModel.channel.in_(channels))
            if min_priority is not None:
                query = query.filter(VectorMetadataModel.priority <= min_priority)
            return query.all()

    def upsert_canon_domain(self, domain: CanonDomain, workspace_id: str = "default") -> None:
        with self.session() as s:
            existing = s.get(CanonDomainModel, str(domain.id))
            if existing:
                for k, v in _to_db(domain.model_dump()).items():
                    if k != "id":
                        setattr(existing, k, v)
            else:
                data = _to_db(domain.model_dump())
                data["workspace_id"] = workspace_id
                s.add(CanonDomainModel(**data))
            s.commit()
        _invalidate_graph()

    upsert_house = upsert_canon_domain  # Deprecated alias

    def get_canon_domain(self, domain_id: UUID) -> CanonDomain | None:
        with self.session() as s:
            row = s.get(CanonDomainModel, str(domain_id))
            if not row:
                return None
            return _domain_from_row(row)

    get_house = get_canon_domain  # Deprecated alias

    def get_house_workspace_id(self, domain_id: UUID) -> str | None:
        with self.session() as s:
            row = s.get(CanonDomainModel, str(domain_id))
            return row.workspace_id if row else None

    def get_canon_domain_by_name(self, name: str) -> CanonDomain | None:
        with self.session() as s:
            row = s.query(CanonDomainModel).filter(CanonDomainModel.name == name).first()
            if not row:
                return None
            return _domain_from_row(row)

    get_house_by_name = get_canon_domain_by_name  # Deprecated alias

    def upsert_canon_entry(self, entry: CanonEntry) -> None:
        with self.session() as s:
            channel_models = []
            if entry.channels:
                for ch in entry.channels:
                    ch_id = getattr(ch, "value", str(ch))
                    ch_model = s.get(ChannelModel, ch_id)
                    if ch_model:
                        channel_models.append(ch_model)

            existing = s.get(CanonEntryModel, str(entry.id))
            data = _to_db(entry.model_dump())
            data.pop("channels", None)

            if existing:
                for k, v in data.items():
                    if k != "id":
                        setattr(existing, k, v)
                existing.channels = channel_models
            else:
                db_entry = CanonEntryModel(**data)
                db_entry.channels = channel_models
                s.add(db_entry)
            s.commit()
        _invalidate_graph()

    upsert_key_message = upsert_canon_entry  # Deprecated alias

    def get_canon_entries(self, domain_id: UUID) -> list[CanonEntry]:
        with self.session() as s:
            rows = (
                s.query(CanonEntryModel)
                .filter(CanonEntryModel.canon_domain_id == str(domain_id))
                .order_by(CanonEntryModel.priority)
                .all()
            )
            return [_entry_from_row(r) for r in rows]

    get_key_messages = get_canon_entries  # Deprecated alias

    def get_canon_entry(self, entry_id: UUID) -> CanonEntry | None:
        with self.session() as s:
            row = s.get(CanonEntryModel, str(entry_id))
            return _entry_from_row(row) if row else None

    get_key_message = get_canon_entry  # Deprecated alias

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

    def get_personas(self, domain_id: UUID) -> list[Persona]:
        with self.session() as s:
            rows = (
                s.query(PersonaModel)
                .filter(PersonaModel.canon_domain_id == str(domain_id))
                .all()
            )
            return [_persona_from_row(r) for r in rows]

    def get_persona_by_name(self, domain_id: UUID, name: str) -> Persona | None:
        with self.session() as s:
            row = (
                s.query(PersonaModel)
                .filter(PersonaModel.canon_domain_id == str(domain_id), PersonaModel.name == name)
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
            row = s.get(CanonEntryModel, chunk_id)
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

    def delete_canon_domain(self, domain_id: UUID) -> bool:
        with self.session() as s:
            row = s.get(CanonDomainModel, str(domain_id))
            if row:
                s.delete(row)
                s.commit()
                _invalidate_graph()
                return True
            return False

    delete_house = delete_canon_domain  # Deprecated alias

    # --- Review Logs ---

    def log_review_action(
        self,
        domain_id: Optional[UUID] = None,
        action: str = "",
        performed_by: str = "",
        entry_id: Optional[UUID] = None,
        notes: str = "",
        # Compatibility arguments
        house_id: Optional[UUID] = None,
        message_id: Optional[UUID] = None,
    ) -> None:
        """Append a review action to the audit trail."""
        actual_domain_id = domain_id or house_id
        actual_entry_id = entry_id or message_id
        with self.session() as s:
            s.add(ReviewLogModel(
                id=str(_uuid.uuid4()),
                canon_domain_id=str(actual_domain_id),
                canon_entry_id=str(actual_entry_id) if actual_entry_id else None,
                action=action,
                performed_by=performed_by,
                timestamp=_now(),
                notes=notes,
            ))
            s.commit()

    def get_review_trail(self, domain_id: UUID) -> list[dict]:
        """Return all review log entries for a domain, newest first."""
        with self.session() as s:
            rows = (
                s.query(ReviewLogModel)
                .filter(ReviewLogModel.canon_domain_id == str(domain_id))
                .order_by(ReviewLogModel.timestamp.desc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "domain_id": r.canon_domain_id,
                    "house_id": r.canon_domain_id,
                    "entry_id": r.canon_entry_id,
                    "message_id": r.canon_entry_id,
                    "action": r.action,
                    "performed_by": r.performed_by,
                    "timestamp": r.timestamp.isoformat(),
                    "notes": r.notes,
                }
                for r in rows
            ]

    def update_house_last_reviewed(self, domain_id: UUID) -> None:
        """Set last_reviewed=now on a domain."""
        with self.session() as s:
            row = s.get(CanonDomainModel, str(domain_id))
            if row:
                row.last_reviewed = _now()
                s.commit()

    def delete_canon_domains_by_source_id(self, source_id: str) -> int:
        """Delete all domains with the given source_id. Returns count deleted."""
        with self.session() as s:
            rows = s.query(CanonDomainModel).filter(CanonDomainModel.source_id == source_id).all()
            count = len(rows)
            for row in rows:
                s.delete(row)
            if count:
                s.commit()
                _invalidate_graph()
            return count

    delete_houses_by_source_id = delete_canon_domains_by_source_id  # Deprecated alias

    def delete_canon_entry(self, entry_id: UUID) -> bool:
        with self.session() as s:
            row = s.get(CanonEntryModel, str(entry_id))
            if row:
                s.delete(row)
                s.commit()
                _invalidate_graph()
                return True
            return False

    delete_key_message = delete_canon_entry  # Deprecated alias

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

    def create_pillar(self, domain_id: UUID, name: str, description: str | None = None, display_order: int = 0) -> int:
        """Insert a new pillar, return its id."""
        with self.session() as s:
            row = PillarModel(
                canon_domain_id=str(domain_id),
                name=name,
                description=description or "",
                display_order=display_order,
            )
            s.add(row)
            s.commit()
            return row.id
        _invalidate_graph()

    def list_pillars(self, domain_id: UUID) -> list["Pillar"]:
        """Return all pillars for a domain ordered by display_order."""
        with self.session() as s:
            rows = (
                s.query(PillarModel)
                .filter(PillarModel.canon_domain_id == str(domain_id))
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
        """Delete pillar; SET NULL cascades to canon_entries. Returns True if found."""
        with self.session() as s:
            row = s.get(PillarModel, pillar_id)
            if not row:
                return False
            s.delete(row)
            s.commit()
            _invalidate_graph()
            return True

    def assign_chunk_to_pillar(self, chunk_id: UUID, pillar_id: int | None) -> bool:
        """Set canon_entries.pillar_id. Pass None to unassign."""
        with self.session() as s:
            row = s.get(CanonEntryModel, str(chunk_id))
            if not row:
                return False
            row.pillar_id = pillar_id
            s.commit()
            _invalidate_graph()
            return True

    # --- Snapshots ---

    def create_snapshot(self, domain_id: UUID, label: str = "") -> dict:
        domain = self.get_canon_domain(domain_id)
        if not domain:
            raise ValueError(f"Domain {domain_id} not found")
        entries = self.get_canon_entries(domain_id)
        personas = self.get_personas(domain_id)
        snapshot_data = {
            "domain": {
                "id": str(domain.id),
                "name": domain.name,
                "source": domain.source,
                "summary": domain.summary,
                "audience": domain.audience,
                "brand_personality": domain.brand_personality,
                "positioning": domain.positioning,
                "tagline": domain.tagline,
                "differentiation": domain.differentiation,
                "status": str(domain.status),
            },
            # Compatibility key:
            "house": {
                "id": str(domain.id),
                "name": domain.name,
                "source": domain.source,
                "summary": domain.summary,
                "audience": domain.audience,
                "brand_personality": domain.brand_personality,
                "positioning": domain.positioning,
                "tagline": domain.tagline,
                "differentiation": domain.differentiation,
                "status": str(domain.status),
            },
            "entries": [
                {
                    "id": str(e.id),
                    "section_type": str(e.section_type),
                    "priority": e.priority,
                    "content": e.content,
                    "variants": e.variants,
                    "personas": e.personas,
                    "channels": [str(c) for c in e.channels],
                }
                for e in entries
            ],
            # Compatibility key:
            "messages": [
                {
                    "id": str(e.id),
                    "section_type": str(e.section_type),
                    "priority": e.priority,
                    "content": e.content,
                    "variants": e.variants,
                    "personas": e.personas,
                    "channels": [str(c) for c in e.channels],
                }
                for e in entries
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
                canon_domain_id=str(domain_id),
                label=label or f"Snapshot {now.strftime('%Y-%m-%d %H:%M')}",
                snapshot_json=snapshot_data,
                created_at=now,
            ))
            s.commit()
        return {"id": snap_id, "domain_id": str(domain_id), "house_id": str(domain_id), "label": label, "created_at": now.isoformat()}

    def list_snapshots(self, domain_id: UUID) -> list[dict]:
        with self.session() as s:
            rows = (
                s.query(SnapshotModel)
                .filter(SnapshotModel.canon_domain_id == str(domain_id))
                .order_by(SnapshotModel.created_at.desc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "domain_id": r.canon_domain_id,
                    "house_id": r.canon_domain_id,
                    "label": r.label,
                    "created_at": r.created_at.isoformat(),
                    "entry_count": len(r.snapshot_json.get("entries", [])),
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
                "domain_id": row.canon_domain_id,
                "house_id": row.canon_domain_id,
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
        """Compare a snapshot against the current state of its domain."""
        snap = self.get_snapshot(snapshot_id)
        if not snap:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        snap_data = snap["snapshot_json"]
        domain_id = UUID(snap_data.get("domain", snap_data.get("house"))["id"])

        current_domain = self.get_canon_domain(domain_id)
        if not current_domain:
            raise ValueError("Domain no longer exists")

        current_entries = self.get_canon_entries(domain_id)
        current_personas = self.get_personas(domain_id)

        field_changes = {}
        snap_domain = snap_data.get("domain", snap_data.get("house"))
        for field in ("name", "summary", "audience", "brand_personality", "positioning", "tagline", "differentiation"):
            snap_val = snap_domain.get(field, "")
            curr_val = getattr(current_domain, field, "") or ""
            if snap_val != curr_val:
                field_changes[field] = {"snapshot": snap_val, "current": curr_val}

        snap_entries = {e["id"]: e for e in snap_data.get("entries", snap_data.get("messages", []))}
        curr_entries = {str(e.id): e for e in current_entries}

        added_entries = [
            {"id": eid, "content": e.content, "section_type": str(e.section_type)}
            for eid, e in curr_entries.items() if eid not in snap_entries
        ]
        removed_entries = [
            {"id": eid, "content": e["content"], "section_type": e["section_type"]}
            for eid, e in snap_entries.items() if eid not in curr_entries
        ]
        changed_entries = []
        for eid in snap_entries:
            if eid in curr_entries:
                snap_e = snap_entries[eid]
                curr_e = curr_entries[eid]
                if snap_e["content"] != curr_e.content:
                    changed_entries.append({
                        "id": eid,
                        "snapshot_content": snap_e["content"],
                        "current_content": curr_e.content,
                        "section_type": str(curr_e.section_type),
                    })

        snap_personas = {p["id"]: p for p in snap_data.get("personas", [])}
        curr_personas = {str(p.id): p for p in current_personas}
        added_personas = [{"id": pid, "name": p.name} for pid, p in curr_personas.items() if pid not in snap_personas]
        removed_personas = [{"id": pid, "name": p["name"]} for pid, p in snap_personas.items() if pid not in curr_personas]

        return {
            "snapshot_id": str(snapshot_id),
            "snapshot_label": snap["label"],
            "snapshot_created_at": snap["created_at"],
            "domain_id": str(domain_id),
            "house_id": str(domain_id),
            "field_changes": field_changes,
            "entries": {
                "added": added_entries,
                "removed": removed_entries,
                "changed": changed_entries,
            },
            # Compatibility key:
            "messages": {
                "added": added_entries,
                "removed": removed_entries,
                "changed": changed_entries,
            },
            "personas": {
                "added": added_personas,
                "removed": removed_personas,
            },
            "has_changes": bool(field_changes or added_entries or removed_entries or changed_entries or added_personas or removed_personas),
        }

    # --- Artifact History ---

    def save_artifact(self, house_id: UUID, skill_id: str, house_name: str,
                       sections: dict, raw_content: str = "", alignment_score: int | None = None) -> dict:
        art_id = str(uuid4())
        now = _now()
        with self.session() as s:
            s.add(ArtifactHistoryModel(
                id=art_id,
                canon_domain_id=str(house_id),
                skill_id=skill_id,
                house_name=house_name,
                sections_json=sections,
                raw_content=raw_content,
                alignment_score=alignment_score,
                created_at=now,
            ))
            s.commit()
        return {"id": art_id, "domain_id": str(house_id), "house_id": str(house_id), "skill_id": skill_id, "alignment_score": alignment_score, "created_at": now.isoformat()}

    def list_artifacts(self, domain_id: UUID) -> list[dict]:
        with self.session() as s:
            rows = (
                s.query(ArtifactHistoryModel)
                .filter(ArtifactHistoryModel.canon_domain_id == str(domain_id))
                .order_by(ArtifactHistoryModel.created_at.desc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "domain_id": r.canon_domain_id,
                    "house_id": r.canon_domain_id,
                    "skill_id": r.skill_id,
                    "house_name": r.house_name,
                    "created_at": r.created_at.isoformat(),
                    "section_count": len(r.sections_json),
                    "alignment_score": getattr(r, "alignment_score", None),
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
                    "domain_id": r.canon_domain_id,
                    "house_id": r.canon_domain_id,
                    "skill_id": r.skill_id,
                    "house_name": r.house_name,
                    "created_at": r.created_at.isoformat(),
                    "alignment_score": getattr(r, "alignment_score", None),
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
                "domain_id": row.canon_domain_id,
                "house_id": row.canon_domain_id,
                "skill_id": row.skill_id,
                "house_name": row.house_name,
                "sections": row.sections_json,
                "raw_content": row.raw_content,
                "status": row.status,
                "alignment_score": getattr(row, "alignment_score", None),
                "created_at": row.created_at.isoformat(),
            }

    def update_artifact_status(self, artifact_id: UUID, status: str) -> bool:
        with self.session() as s:
            row = s.get(ArtifactHistoryModel, str(artifact_id))
            if not row:
                return False
            row.status = status
            s.commit()
            return True

    # --- Artifact Ratings ---

    def rate_artifact(
        self,
        artifact_id: str,
        rating: int,
        tag: str = "good",
        rated_by: str = "",
        notes: str = "",
    ) -> dict:
        """Rate an artifact (1-5 stars, or good/bad tag). Updates chunk usage stats."""
        rating = max(1, min(5, int(rating)))
        tag = tag if tag in ("good", "bad") else ("good" if rating >= 3 else "bad")

        rating_id = str(uuid4())
        now = _now()
        with self.session() as s:
            s.add(ArtifactRatingModel(
                id=rating_id,
                artifact_id=artifact_id,
                rating=rating,
                tag=tag,
                rated_by=rated_by,
                timestamp=now,
                notes=notes,
            ))
            s.commit()

        # Update chunk usage stats based on this rating
        self._update_chunk_stats_from_rating(artifact_id, rating)
        return {"id": rating_id, "artifact_id": artifact_id, "rating": rating, "tag": tag}

    def get_artifact_rating(self, artifact_id: str) -> list[dict]:
        """Get all ratings for an artifact."""
        with self.session() as s:
            rows = (
                s.query(ArtifactRatingModel)
                .filter(ArtifactRatingModel.artifact_id == artifact_id)
                .order_by(ArtifactRatingModel.timestamp.desc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "artifact_id": r.artifact_id,
                    "rating": r.rating,
                    "tag": r.tag,
                    "rated_by": r.rated_by,
                    "timestamp": r.timestamp.isoformat(),
                    "notes": r.notes,
                }
                for r in rows
            ]

    def _update_chunk_stats_from_rating(self, artifact_id: str, rating: int) -> None:
        """Update chunk_usage_stats for chunks used in this artifact."""
        artifact = self.get_artifact(UUID(artifact_id))
        if not artifact:
            return
        sections = artifact.get("sections", {})
        # Extract chunk_ids from sections (they may reference chunks)
        chunk_ids = self._extract_chunk_ids_from_sections(sections)
        for chunk_id in chunk_ids:
            self.record_chunk_usage(chunk_id, rating)

    def _extract_chunk_ids_from_sections(self, sections: dict) -> list[str]:
        """Extract chunk IDs referenced in artifact sections."""
        import re
        chunk_ids = []
        # Look for chunk references in section content
        for section_key, content in (sections or {}).items():
            if isinstance(content, str):
                # Look for chunk-{uuid} patterns
                found = re.findall(r"chunk-([0-9a-fA-F-]+)", content)
                chunk_ids.extend(found)
        return chunk_ids

    def record_chunk_usage(self, chunk_id: str, artifact_rating: int) -> None:
        """Record that a chunk was used in an artifact, update stats."""
        with self.session() as s:
            row = s.get(ChunkUsageStatModel, chunk_id)
            if row:
                # Update running average
                old_total = row.avg_rating * row.times_used
                row.times_used += 1
                row.avg_rating = (old_total + artifact_rating) / row.times_used
                # Boost factor: higher for highly-rated usage
                if row.avg_rating >= 4.0:
                    row.boost_factor = min(2.0, 1.0 + (row.avg_rating - 3.0) * 0.25)
                elif row.avg_rating <= 2.0:
                    row.boost_factor = max(0.5, row.avg_rating * 0.5)
                else:
                    row.boost_factor = 1.0
            else:
                s.add(ChunkUsageStatModel(
                    chunk_id=chunk_id,
                    times_used=1,
                    avg_rating=float(artifact_rating),
                    boost_factor=1.5 if artifact_rating >= 4 else (0.8 if artifact_rating <= 2 else 1.0),
                ))
            s.commit()

    # --- Chunk Usage Heatmap & Coverage ---

    def get_chunk_usage_heatmap(self, domain_id: UUID) -> dict:
        """Get usage heatmap: how many times each chunk was used, with which ratings."""
        entries = self.get_canon_entries(domain_id)
        entry_id_to_entry = {str(e.id): e for e in entries}

        with self.session() as s:
            stats_rows = s.query(ChunkUsageStatModel).all()
            # Get all ratings for artifacts in this domain
            artifact_rows = (
                s.query(ArtifactHistoryModel)
                .filter(ArtifactHistoryModel.canon_domain_id == str(domain_id))
                .all()
            )
            artifact_ids = [r.id for r in artifact_rows]
            ratings_rows = []
            if artifact_ids:
                ratings_rows = (
                    s.query(ArtifactRatingModel)
                    .filter(ArtifactRatingModel.artifact_id.in_(artifact_ids))
                    .all()
                )

        # Build heatmap
        heatmap = {}
        for stat in stats_rows:
            chunk_id = stat.chunk_id
            # Check if this chunk belongs to this domain
            e = entry_id_to_entry.get(chunk_id.replace("chunk-", ""))
            if not e and not chunk_id.startswith("chunk-"):
                e = entry_id_to_entry.get(chunk_id)
            if not e:
                continue
            heatmap[chunk_id] = {
                "chunk_id": chunk_id,
                "content_preview": e.content[:100] if e else "",
                "section_type": str(e.section_type) if e else "",
                "times_used": stat.times_used,
                "avg_rating": round(stat.avg_rating, 2),
                "boost_factor": round(stat.boost_factor, 2),
                "priority": e.priority if e else 0,
            }

        return {
            "domain_id": str(domain_id),
            "house_id": str(domain_id),
            "chunks": list(heatmap.values()),
            "total_chunks_used": len(heatmap),
            "avg_boost": round(
                sum(v["boost_factor"] for v in heatmap.values()) / max(len(heatmap), 1), 2
            ),
        }

    def get_canon_domain_coverage(self, domain_id: UUID) -> dict:
        """Which parts of the canon domain are used most vs ignored."""
        entries = self.get_canon_entries(domain_id)
        personas = self.get_personas(domain_id)

        with self.session() as s:
            stats_rows = s.query(ChunkUsageStatModel).all()

        used_chunk_ids = {s.chunk_id for s in stats_rows}
        used_times = {s.chunk_id: s.times_used for s in stats_rows}

        # Group by section type
        by_section: dict = {}
        for e in entries:
            chunk_id = f"chunk-{e.id}"
            st = str(e.section_type)
            item = by_section.setdefault(st, {"used": 0, "unused": 0, "total": 0, "times_used": 0})
            item["total"] += 1
            if chunk_id in used_chunk_ids:
                item["used"] += 1
                item["times_used"] += used_times.get(chunk_id, 0)
            else:
                item["unused"] += 1

        # Most/least used chunks
        chunk_usage = [(s.chunk_id, s.times_used) for s in stats_rows]
        chunk_usage.sort(key=lambda x: x[1], reverse=True)

        # Map chunk_id to content
        entry_map = {f"chunk-{e.id}": e.content[:80] for e in entries}

        return {
            "domain_id": str(domain_id),
            "house_id": str(domain_id),
            "by_section": by_section,
            "most_used": [
                {"chunk_id": cid, "times_used": times, "content": entry_map.get(cid, "")}
                for cid, times in chunk_usage[:10]
            ],
            "unused_chunks": [
                {"chunk_id": f"chunk-{e.id}", "content": e.content[:80], "section_type": str(e.section_type)}
                for e in entries
                if f"chunk-{e.id}" not in used_chunk_ids
            ],
            "persona_coverage": {
                p.name: {
                    "has_messages": any(p.name in (e.personas or []) for e in entries),
                    "message_count": sum(1 for e in entries if p.name in (e.personas or [])),
                }
                for p in personas
            },
        }

    get_message_house_coverage = get_canon_domain_coverage  # Deprecated alias

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

    def get_penpot_project(self, workspace_id: str) -> str | None:
        """Get the Penpot project ID for a workspace."""
        with self.session() as s:
            row = s.get(WorkspaceModel, workspace_id)
            return row.penpot_project_id if row else None

    def set_penpot_project(self, workspace_id: str, project_id: str) -> bool:
        """Set the Penpot project ID for a workspace."""
        with self.session() as s:
            row = s.get(WorkspaceModel, workspace_id)
            if not row:
                return False
            row.penpot_project_id = project_id
            s.commit()
            return True

    # --- Brand Settings ---

    def get_brand_settings(self, workspace_id: str) -> "BrandSettings | None":
        from src.models import BrandSettings
        with self.session() as s:
            row = s.get(BrandSettingsModel, workspace_id)
            if not row:
                return None
            return BrandSettings(
                workspace_id=row.workspace_id,
                primary_color=row.primary_color,
                secondary_color=row.secondary_color,
                accent_color=row.accent_color,
                background_color=row.background_color,
                text_color=row.text_color,
                font_heading=row.font_heading,
                font_body=row.font_body,
                logo_path=row.logo_path,
            )

    def upsert_brand_settings(self, workspace_id: str, **kwargs) -> "BrandSettings":
        from src.models import BrandSettings
        with self.session() as s:
            row = s.get(BrandSettingsModel, workspace_id)
            if row:
                for k, v in kwargs.items():
                    if hasattr(row, k) and k != "workspace_id":
                        setattr(row, k, v)
            else:
                data = {"workspace_id": workspace_id}
                data.update(kwargs)
                row = BrandSettingsModel(**data)
                s.add(row)
            s.commit()
            return BrandSettings(
                workspace_id=row.workspace_id,
                primary_color=row.primary_color,
                secondary_color=row.secondary_color,
                accent_color=row.accent_color,
                background_color=row.background_color,
                text_color=row.text_color,
                font_heading=row.font_heading,
                font_body=row.font_body,
                logo_path=row.logo_path,
            )

    def upload_logo(self, workspace_id: str, file_path: str) -> str:
        import shutil
        from pathlib import Path

        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"Logo file not found: {file_path}")

        brand_dir = Path("data/brand") / workspace_id
        brand_dir.mkdir(parents=True, exist_ok=True)

        dest = brand_dir / src.name
        shutil.copy2(src, dest)

        logo_path = str(dest)
        self.upsert_brand_settings(workspace_id, logo_path=logo_path)
        return logo_path

    # --- Brand Assets ---

    def upload_brand_asset(self, workspace_id: str, file_path: str, asset_type: str) -> dict:
        """Upload a brand asset (logo, icon, image) for a workspace."""
        import shutil
        from pathlib import Path
        from os import path

        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"Asset file not found: {file_path}")

        # Store in data/brand/{workspace_id}/assets/
        asset_dir = Path("data/brand") / workspace_id / "assets"
        asset_dir.mkdir(parents=True, exist_ok=True)

        dest = asset_dir / src.name
        shutil.copy2(src, dest)

        asset_id = str(uuid4())
        now = _now()
        asset_name = src.name

        with self.session() as s:
            s.add(BrandAssetModel(
                id=asset_id,
                workspace_id=workspace_id,
                asset_name=asset_name,
                asset_type=asset_type,
                file_path=str(dest),
                mime_type="image/png",  # Could be detected from file
                file_size=path.getsize(src),
                created_at=now,
                updated_at=now,
            ))
            s.commit()

        return {
            "id": asset_id,
            "workspace_id": workspace_id,
            "asset_name": asset_name,
            "asset_type": asset_type,
            "file_path": str(dest),
            "created_at": now.isoformat(),
        }

    def get_brand_asset(self, workspace_id: str, asset_name: str) -> dict | None:
        """Get a brand asset by name for a workspace."""
        with self.session() as s:
            row = (
                s.query(BrandAssetModel)
                .filter(
                    BrandAssetModel.workspace_id == workspace_id,
                    BrandAssetModel.asset_name == asset_name,
                )
                .first()
            )
            if not row:
                return None
            return {
                "id": row.id,
                "workspace_id": row.workspace_id,
                "asset_name": row.asset_name,
                "asset_type": row.asset_type,
                "file_path": row.file_path,
                "mime_type": row.mime_type,
                "file_size": row.file_size,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            }

    def list_brand_assets(self, workspace_id: str) -> list[dict]:
        """List all brand assets for a workspace."""
        with self.session() as s:
            rows = (
                s.query(BrandAssetModel)
                .filter(BrandAssetModel.workspace_id == workspace_id)
                .order_by(BrandAssetModel.created_at.desc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "workspace_id": r.workspace_id,
                    "asset_name": r.asset_name,
                    "asset_type": r.asset_type,
                    "file_path": r.file_path,
                    "mime_type": r.mime_type,
                    "file_size": r.file_size,
                    "created_at": r.created_at.isoformat(),
                    "updated_at": r.updated_at.isoformat(),
                }
                for r in rows
            ]

    def delete_brand_asset(self, workspace_id: str, asset_name: str) -> bool:
        """Delete a brand asset."""
        from pathlib import Path

        with self.session() as s:
            row = (
                s.query(BrandAssetModel)
                .filter(
                    BrandAssetModel.workspace_id == workspace_id,
                    BrandAssetModel.asset_name == asset_name,
                )
                .first()
            )
            if not row:
                return False
            
            # Delete the file
            try:
                Path(row.file_path).unlink(missing_ok=True)
            except Exception:
                pass
            
            s.delete(row)
            s.commit()
            return True

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

    def get_channel(self, channel_id: str) -> dict | None:
        with self.session() as s:
            r = s.get(ChannelModel, channel_id)
            if not r:
                return None
            return {"id": r.id, "name": r.name, "description": r.description, "is_custom": r.is_custom}

    def create_channel(self, name: str, description: str = "") -> dict:
        """Create a user-defined custom channel. ID is slugified from name."""
        import re
        channel_id = re.sub(r"[^a-z0-9_]", "_", name.lower().strip())
        with self.session() as s:
            existing = s.get(ChannelModel, channel_id)
            if existing:
                raise ValueError(f"Channel '{channel_id}' already exists")
            ch = ChannelModel(id=channel_id, name=name, description=description, is_custom=True, created_at=_now())
            s.add(ch)
            s.commit()
            return {"id": ch.id, "name": ch.name, "description": ch.description, "is_custom": ch.is_custom}

    def update_channel(self, channel_id: str, name: str | None = None, description: str | None = None) -> dict | None:
        with self.session() as s:
            ch = s.get(ChannelModel, channel_id)
            if not ch:
                return None
            if not ch.is_custom:
                raise ValueError("Cannot edit built-in channels")
            if name is not None:
                ch.name = name
            if description is not None:
                ch.description = description
            s.commit()
            return {"id": ch.id, "name": ch.name, "description": ch.description, "is_custom": ch.is_custom}

    def delete_channel(self, channel_id: str) -> bool:
        with self.session() as s:
            ch = s.get(ChannelModel, channel_id)
            if not ch:
                return False
            if not ch.is_custom:
                raise ValueError("Cannot delete built-in channels")
            s.delete(ch)
            s.commit()
            return True

    def get_channels(self) -> list[dict]:
        """Return all channels ordered: built-ins first, then custom alphabetically."""
        with self.session() as s:
            rows = s.query(ChannelModel).order_by(ChannelModel.is_custom, ChannelModel.name).all()
            return [{"id": r.id, "name": r.name, "description": r.description, "is_custom": r.is_custom} for r in rows]

    def upsert_channel(self, ch_id: str, name: str, description: str = "") -> dict:
        """Backward-compat: create or update a channel by explicit ID."""
        with self.session() as s:
            existing = s.get(ChannelModel, ch_id)
            if existing:
                existing.name = name
                existing.description = description
            else:
                s.add(ChannelModel(id=ch_id, name=name, description=description,
                                   is_custom=True, created_at=_now()))
            s.commit()
            row = s.get(ChannelModel, ch_id)
            return {"id": row.id, "name": row.name, "description": row.description,
                    "is_custom": row.is_custom, "created_at": row.created_at.isoformat()}

    def get_channel_message_count(self, channel_id: str) -> int:
        """Count how many key messages are associated with a channel."""
        from sqlalchemy import select, func
        with self.session() as s:
            result = s.execute(
                select(func.count()).select_from(canon_entry_channel_association).where(
                    canon_entry_channel_association.c.channel_id == channel_id
                )
            ).scalar()
            return result or 0

    # --- Workspace-scoped domain list ---

    def list_canon_domains(self, workspace_id: str | None = None) -> list[CanonDomain]:
        with self.session() as s:
            q = s.query(CanonDomainModel)
            if workspace_id and workspace_id != "all":
                q = q.filter(CanonDomainModel.workspace_id == workspace_id)
            rows = q.all()
            return [_domain_from_row(r) for r in rows]

    list_houses = list_canon_domains  # Deprecated alias

    def list_canon_domains_with_counts(self, workspace_id: str | None = None) -> list[dict]:
        """Return domains with pre-aggregated entry/persona counts — avoids N+1."""
        from sqlalchemy import func
        with self.session() as s:
            entry_counts = (
                s.query(CanonEntryModel.canon_domain_id, func.count().label("cnt"))
                .group_by(CanonEntryModel.canon_domain_id)
                .subquery()
            )
            persona_counts = (
                s.query(PersonaModel.canon_domain_id, func.count().label("cnt"))
                .group_by(PersonaModel.canon_domain_id)
                .subquery()
            )
            q = (
                s.query(
                    CanonDomainModel,
                    func.coalesce(entry_counts.c.cnt, 0).label("entry_count"),
                    func.coalesce(persona_counts.c.cnt, 0).label("persona_count"),
                )
                .outerjoin(entry_counts, CanonDomainModel.id == entry_counts.c.canon_domain_id)
                .outerjoin(persona_counts, CanonDomainModel.id == persona_counts.c.canon_domain_id)
            )
            if workspace_id and workspace_id != "all":
                q = q.filter(CanonDomainModel.workspace_id == workspace_id)
            return [
                {
                    "domain": _domain_from_row(row),
                    "entry_count": int(ec),
                    "persona_count": int(pc),
                    # Backward-compat keys
                    "house": _domain_from_row(row),
                    "message_count": int(ec),
                }
                for row, ec, pc in q.all()
            ]

    list_houses_with_counts = list_canon_domains_with_counts  # Deprecated alias

    # --- Source Connections ---

    def create_connection(
        self,
        provider: str,
        folder_id: str,
        account_email: str,
        folder_name: str,
        access_token: str,
        refresh_token: str,
        page_token: str,
        workspace_id: str = "default",
    ) -> dict:
        row = SourceConnectionModel(
            id=str(uuid4()),
            workspace_id=workspace_id,
            provider=provider,
            account_email=account_email,
            folder_id=folder_id,
            folder_name=folder_name,
            access_token=access_token,
            refresh_token=refresh_token,
            page_token=page_token,
            status="connected",
            created_at=_now(),
        )
        with self.session() as s:
            s.add(row)
            s.commit()
            return _conn_to_dict(row)

    def get_connection(self, connection_id: str) -> dict | None:
        with self.session() as s:
            row = s.get(SourceConnectionModel, connection_id)
            return _conn_to_dict(row) if row else None

    def list_connections(self, workspace_id: str | None = None) -> list[dict]:
        with self.session() as s:
            q = s.query(SourceConnectionModel)
            if workspace_id:
                q = q.filter(SourceConnectionModel.workspace_id == workspace_id)
            return [_conn_to_dict(r) for r in q.order_by(SourceConnectionModel.created_at).all()]

    def update_connection(self, connection_id: str, updates: dict) -> None:
        with self.session() as s:
            row = s.get(SourceConnectionModel, connection_id)
            if not row:
                return
            for k, v in updates.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            s.commit()

    def delete_connection(self, connection_id: str) -> bool:
        with self.session() as s:
            row = s.get(SourceConnectionModel, connection_id)
            if not row:
                return False
            s.delete(row)
            s.commit()
            return True

    # --- Source Files ---

    def upsert_source_file(
        self,
        connection_id: str,
        drive_file_id: str,
        file_name: str,
        mime_type: str = "",
        drive_modified_at: str = "",
        house_id: str | None = None,
        sync_status: str = "synced",
        error_message: str = "",
    ) -> None:
        with self.session() as s:
            row = (
                s.query(SourceFileModel)
                .filter(
                    SourceFileModel.connection_id == connection_id,
                    SourceFileModel.drive_file_id == drive_file_id,
                )
                .first()
            )
            now = _now()
            if row:
                row.file_name = file_name
                row.mime_type = mime_type
                row.drive_modified_at = drive_modified_at
                row.sync_status = sync_status
                row.error_message = error_message
                row.synced_at = now
                if house_id is not None:
                    row.canon_domain_id = house_id
            else:
                s.add(SourceFileModel(
                    id=str(uuid4()),
                    connection_id=connection_id,
                    drive_file_id=drive_file_id,
                    file_name=file_name,
                    mime_type=mime_type,
                    canon_domain_id=house_id,
                    drive_modified_at=drive_modified_at,
                    sync_status=sync_status,
                    error_message=error_message,
                    synced_at=now,
                ))
            s.commit()

    def get_source_file_by_drive_id(self, connection_id: str, drive_file_id: str) -> dict | None:
        with self.session() as s:
            row = (
                s.query(SourceFileModel)
                .filter(
                    SourceFileModel.connection_id == connection_id,
                    SourceFileModel.drive_file_id == drive_file_id,
                )
                .first()
            )
            return _source_file_to_dict(row) if row else None

    def list_source_files(self, connection_id: str) -> list[dict]:
        with self.session() as s:
            rows = (
                s.query(SourceFileModel)
                .filter(SourceFileModel.connection_id == connection_id)
                .order_by(SourceFileModel.file_name)
                .all()
            )
            return [_source_file_to_dict(r) for r in rows]

    def delete_source_file(self, connection_id: str, drive_file_id: str) -> None:
        with self.session() as s:
            row = (
                s.query(SourceFileModel)
                .filter(
                    SourceFileModel.connection_id == connection_id,
                    SourceFileModel.drive_file_id == drive_file_id,
                )
                .first()
            )
            if row:
                s.delete(row)
                s.commit()

    # ── Phase 3: Entry Approval Workflow ────────────────────────────────────

    def update_entry_status(self, entry_id: str, status: str, approved_by: str = "", notes: str = "") -> dict | None:
        """Update canon entry status and log the action to review_logs."""
        valid = {"draft", "in_review", "approved", "outdated", "locked"}
        if status not in valid:
            raise ValueError(f"Invalid status. Must be one of: {valid}")
        with self.session() as s:
            entry = s.get(CanonEntryModel, entry_id)
            if not entry:
                return None
            entry.status = status
            if status == "approved":
                entry.approved_by = approved_by or "admin"
                entry.approved_at = _now()
            log = ReviewLogModel(
                id=str(uuid4()),
                canon_domain_id=entry.canon_domain_id,
                canon_entry_id=entry_id,
                action=status,
                performed_by=approved_by or "admin",
                timestamp=_now(),
                notes=notes,
            )
            s.add(log)
            s.commit()
            return {"id": entry_id, "status": entry.status, "approved_by": entry.approved_by}

    update_message_status = update_entry_status  # Deprecated alias

    def bulk_update_entry_status(self, entry_ids: list[str], status: str, approved_by: str = "") -> int:
        """Bulk update status for multiple entries. Returns count updated."""
        updated = 0
        for eid in entry_ids:
            result = self.update_entry_status(eid, status, approved_by)
            if result:
                updated += 1
        return updated

    bulk_update_message_status = bulk_update_entry_status  # Deprecated alias

    def get_review_log(self, house_id: str, limit: int = 50) -> list[dict]:
        with self.session() as s:
            rows = (
                s.query(ReviewLogModel)
                .filter(ReviewLogModel.canon_domain_id == str(house_id))
                .order_by(ReviewLogModel.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "message_id": r.canon_entry_id,
                    "entry_id": r.canon_entry_id,
                    "action": r.action,
                    "performed_by": r.performed_by,
                    "timestamp": r.timestamp.isoformat(),
                    "notes": r.notes,
                }
                for r in rows
            ]

    # ── Phase 4: Staleness / Last Reviewed ───────────────────────────────────

    def mark_domain_reviewed(self, domain_id: str, reviewed_by: str = "admin") -> dict | None:
        """Set last_reviewed = now() and append a review log entry."""
        with self.session() as s:
            domain = s.get(CanonDomainModel, str(domain_id))
            if not domain:
                return None
            domain.last_reviewed = _now()
            log = ReviewLogModel(
                id=str(uuid4()),
                canon_domain_id=str(domain_id),
                canon_entry_id=None,
                action="reviewed",
                performed_by=reviewed_by,
                timestamp=_now(),
                notes="Canon domain marked as reviewed",
            )
            s.add(log)
            s.commit()
            return {"domain_id": str(domain_id), "house_id": str(domain_id), "last_reviewed": domain.last_reviewed.isoformat()}

    mark_house_reviewed = mark_domain_reviewed  # Deprecated alias

    def get_stale_domains(self, days: int = 90) -> list[dict]:
        """Return domains not reviewed in the last `days` days."""
        from datetime import timedelta
        cutoff = _now() - timedelta(days=days)
        with self.session() as s:
            rows = s.query(CanonDomainModel).filter(
                (CanonDomainModel.last_reviewed == None) | (CanonDomainModel.last_reviewed < cutoff)  # noqa: E711
            ).all()
            return [
                {
                    "id": r.id,
                    "domain_id": r.id,
                    "house_id": r.id,
                    "name": r.name,
                    "last_reviewed": r.last_reviewed.isoformat() if r.last_reviewed else None,
                }
                for r in rows
            ]

    get_stale_houses = get_stale_domains  # Deprecated alias

    # ── Phase 5: Feedback Loop ────────────────────────────────────────────────

    def record_artifact_rating(self, artifact_id: str, rating: int, tag: str = "good", rated_by: str = "", notes: str = "") -> dict:
        """Save artifact rating and update chunk boost factors for used messages."""
        if not (1 <= rating <= 5):
            raise ValueError("Rating must be 1-5")
        with self.session() as s:
            rating_row = ArtifactRatingModel(
                id=str(uuid4()),
                artifact_id=artifact_id,
                rating=rating,
                tag=tag,
                rated_by=rated_by,
                timestamp=_now(),
                notes=notes,
            )
            s.add(rating_row)
            artifact = s.get(ArtifactHistoryModel, artifact_id)
            if artifact:
                sections = artifact.sections_json or {}
                chunk_ids: set[str] = set()
                for section_list in sections.values():
                    if isinstance(section_list, list):
                        for item in section_list:
                            cid = item.get("source_chunk_id") if isinstance(item, dict) else None
                            if cid:
                                chunk_ids.add(cid)
                for chunk_id in chunk_ids:
                    stat = s.get(ChunkUsageStatModel, chunk_id)
                    if not stat:
                        stat = ChunkUsageStatModel(chunk_id=chunk_id, times_used=0, avg_rating=0.0, boost_factor=1.0)
                        s.add(stat)
                    total = stat.times_used * stat.avg_rating + rating
                    stat.times_used += 1
                    stat.avg_rating = total / stat.times_used
                    # Boost range: 0.8–1.2 centred on 3.0 baseline
                    stat.boost_factor = max(0.8, min(1.2, 1.0 + (stat.avg_rating - 3.0) * 0.1))
            s.commit()
            return {"id": rating_row.id, "artifact_id": artifact_id, "rating": rating, "tag": tag}

    def get_entry_usage_stats(self, domain_id: str) -> list[dict]:
        """Return canon entries with usage stats for the heatmap, sorted by times_used desc."""
        with self.session() as s:
            entries = s.query(CanonEntryModel).filter(
                CanonEntryModel.canon_domain_id == str(domain_id)
            ).all()
            result = []
            for e in entries:
                stat = s.get(ChunkUsageStatModel, e.source_chunk_id) if e.source_chunk_id else None
                result.append({
                    "id": e.id,
                    "content": e.content,
                    "section_type": e.section_type,
                    "status": e.status,
                    "times_used": stat.times_used if stat else 0,
                    "avg_rating": round(stat.avg_rating, 1) if stat else 0.0,
                    "boost_factor": round(stat.boost_factor, 2) if stat else 1.0,
                })
            result.sort(key=lambda x: x["times_used"], reverse=True)
            return result

    get_message_usage_stats = get_entry_usage_stats  # Deprecated alias


def _conn_to_dict(row: "SourceConnectionModel") -> dict:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "provider": row.provider,
        "account_email": row.account_email,
        "folder_id": row.folder_id,
        "folder_name": row.folder_name,
        "access_token": row.access_token,
        "refresh_token": row.refresh_token,
        "page_token": row.page_token,
        "status": row.status,
        "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat(),
    }


def _source_file_to_dict(row: "SourceFileModel") -> dict:
    return {
        "id": row.id,
        "connection_id": row.connection_id,
        "drive_file_id": row.drive_file_id,
        "file_name": row.file_name,
        "mime_type": row.mime_type,
        "domain_id": row.canon_domain_id,
        "house_id": row.canon_domain_id,
        "drive_modified_at": row.drive_modified_at,
        "sync_status": row.sync_status,
        "error_message": row.error_message,
        "synced_at": row.synced_at.isoformat() if row.synced_at else None,
    }


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


def _domain_from_row(row: CanonDomainModel) -> CanonDomain:
    return CanonDomain(
        id=UUID(row.id),
        name=row.name,
        source=row.source,
        source_id=row.source_id,
        document_type=row.document_type if row.document_type else "canon_domain",
        summary=row.summary,
        audience=row.audience,
        brand_personality=row.brand_personality,
        positioning=row.positioning,
        tagline=row.tagline,
        differentiation=row.differentiation,
        status=DomainStatus(row.status),
        last_synced=row.last_synced,
        last_reviewed=row.last_reviewed,
    )


_house_from_row = _domain_from_row  # Deprecated alias


def _entry_from_row(row: CanonEntryModel) -> CanonEntry:
    return CanonEntry(
        id=UUID(row.id),
        canon_domain_id=UUID(row.canon_domain_id),
        pillar_id=row.pillar_id,
        section_type=_safe_section_type(row.section_type),
        priority=row.priority,
        content=row.content,
        status=EntryStatus(row.status) if row.status else EntryStatus.DRAFT,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        variants=row.variants or {},
        personas=row.personas or [],
        channels=[_safe_channel(c.id if hasattr(c, "id") else str(c)) for c in (row.channels or [])] or ["all"],
        source_chunk_id=row.source_chunk_id,
    )


_msg_from_row = _entry_from_row  # Deprecated alias


def _persona_from_row(row: PersonaModel) -> Persona:
    return Persona(
        id=UUID(row.id),
        canon_domain_id=UUID(row.canon_domain_id),
        name=row.name,
        description=row.description,
        pain_points=row.pain_points or [],
        buying_triggers=row.buying_triggers or [],
        objections=row.objections or [],
        status=EntryStatus(row.status) if row.status else EntryStatus.DRAFT,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
    )


def _pillar_from_row(row: PillarModel) -> "Pillar":
    from src.models import Pillar
    return Pillar(
        id=row.id,
        canon_domain_id=row.canon_domain_id,
        name=row.name,
        description=row.description,
        display_order=row.display_order,
    )