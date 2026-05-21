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

from src.models import BrandSettings, Channel, DocumentType, HouseStatus, KeyMessage, MessageHouse, Persona, SectionType


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

# Association table for KeyMessageModel and ChannelModel (many-to-many)
key_message_channel_association = Table(
    "key_message_channel_association",
    Base.metadata,
    Column("key_message_id", String(36), ForeignKey("key_messages.id", ondelete="CASCADE")),
    Column("channel_id", String(50), ForeignKey("channels.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("key_message_id", "channel_id")
)

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
    last_reviewed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

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
    status: Mapped[str] = mapped_column(String(20), default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    variants: Mapped[dict] = mapped_column(JSON, default=dict)
    personas: Mapped[list] = mapped_column(JSON, default=list)
    # Many-to-many relationship with ChannelModel
    channels: Mapped[list["ChannelModel"]] = relationship(
        secondary=key_message_channel_association,
        backref="key_messages"
    )
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
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


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
    house_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    drive_modified_at: Mapped[str] = mapped_column(String(50), default="")
    sync_status: Mapped[str] = mapped_column(String(30), default="pending")
    error_message: Mapped[str] = mapped_column(Text, default="")
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    connection: Mapped["SourceConnectionModel"] = relationship(back_populates="source_files")


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
    house_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("message_houses.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    performed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class VectorMetadataModel(Base):
    __tablename__ = "vector_metadata"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # e.g., 'chunk-UUID', 'field-UUID-field', 'kym-UUID'
    message_house_id: Mapped[str] = mapped_column(String(36), nullable=False)
    house_name: Mapped[str] = mapped_column(String(255), nullable=False)
    house_summary: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section_type: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    persona: Mapped[str] = mapped_column(String(255), default="general")
    channel: Mapped[str] = mapped_column(String(255), default="all")
    key_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_synced: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


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
Index("ix_source_files_conn", SourceFileModel.connection_id)
Index("ix_source_files_drive_id", SourceFileModel.drive_file_id)
Index("ix_review_logs_house_id", ReviewLogModel.house_id)
Index("ix_review_logs_timestamp", ReviewLogModel.timestamp)
Index("ix_artifact_rating_artifact_id", ArtifactRatingModel.artifact_id)
Index("ix_chunk_usage_chunk_id", ChunkUsageStatModel.chunk_id)
Index("ix_vector_metadata_house_id", VectorMetadataModel.message_house_id)


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

            # Add penpot_project_id to workspaces if missing
            if "workspaces" in insp.get_table_names():
                ws_cols = {c["name"] for c in insp.get_columns("workspaces")}
                if "penpot_project_id" not in ws_cols:
                    try:
                        conn.execute(text("ALTER TABLE workspaces ADD COLUMN penpot_project_id TEXT"))
                        conn.commit()
                    except Exception:
                        pass

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

            # Migrate key_messages channels: JSON column → many-to-many association table
            if "key_messages" in insp.get_table_names():
                km_cols = {c["name"] for c in insp.get_columns("key_messages")}

                # Drop the old JSON channels column if it exists
                if "channels" in km_cols:
                    try:
                        conn.execute(text("ALTER TABLE key_messages DROP COLUMN channels"))
                        conn.commit()
                    except Exception as e:
                        print(f"Warning: Could not drop old key_messages.channels JSON column: {e}")

                # Create the association table if not yet present
                if "key_message_channel_association" not in insp.get_table_names():
                    conn.execute(text('''
                        CREATE TABLE key_message_channel_association (
                            key_message_id VARCHAR(36) NOT NULL,
                            channel_id VARCHAR(50) NOT NULL,
                            PRIMARY KEY (key_message_id, channel_id),
                            FOREIGN KEY (key_message_id) REFERENCES key_messages(id) ON DELETE CASCADE,
                            FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
                        )
                    '''))
                    conn.commit()

                # Drop deprecated pain_point_ids and objection_ids JSON columns
                for col in ("pain_point_ids", "objection_ids"):
                    if col in km_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE key_messages DROP COLUMN {col}"))
                            conn.commit()
                        except Exception as e:
                            print(f"Warning: Could not drop old key_messages.{col} JSON column: {e}")

            if "artifact_ratings" not in insp.get_table_names():
                conn.execute(text("""
                    CREATE TABLE artifact_ratings (
                        id TEXT PRIMARY KEY,
                        artifact_id TEXT NOT NULL REFERENCES artifact_history(id) ON DELETE CASCADE,
                        rating INTEGER NOT NULL,
                        tag TEXT NOT NULL DEFAULT 'good',
                        rated_by TEXT NOT NULL DEFAULT '',
                        timestamp DATETIME NOT NULL,
                        notes TEXT NOT NULL DEFAULT ''
                    )
                """))
                conn.commit()

            # Create chunk_usage_stats table if not exists
            if "chunk_usage_stats" not in insp.get_table_names():
                conn.execute(text("""
                    CREATE TABLE chunk_usage_stats (
                        chunk_id TEXT PRIMARY KEY,
                        times_used INTEGER NOT NULL DEFAULT 0,
                        avg_rating FLOAT NOT NULL DEFAULT 0.0,
                        boost_factor FLOAT NOT NULL DEFAULT 1.0
                    )
                """))
                conn.commit()

            # Create source_connections table
            if "source_connections" not in insp.get_table_names():
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

            # Create source_files table
            if "source_files" not in insp.get_table_names():
                conn.execute(text("""
                    CREATE TABLE source_files (
                        id TEXT PRIMARY KEY,
                        connection_id TEXT NOT NULL REFERENCES source_connections(id) ON DELETE CASCADE,
                        drive_file_id TEXT NOT NULL,
                        file_name TEXT NOT NULL,
                        mime_type TEXT DEFAULT '',
                        house_id TEXT,
                        drive_modified_at TEXT DEFAULT '',
                        sync_status TEXT DEFAULT 'pending',
                        error_message TEXT DEFAULT '',
                        synced_at DATETIME
                    )
                """))
                conn.commit()

            # Migrate channels table: is_default -> is_custom
            if "channels" in insp.get_table_names():
                ch_cols = {c["name"] for c in insp.get_columns("channels")}
                if "is_default" in ch_cols and "is_custom" not in ch_cols:
                    conn.execute(text("ALTER TABLE channels ADD COLUMN is_custom BOOLEAN DEFAULT FALSE"))
                    conn.execute(text("UPDATE channels SET is_custom = CASE WHEN is_default = 1 THEN 0 ELSE 1 END"))
                    conn.commit()
                elif "is_custom" not in ch_cols:
                    conn.execute(text("ALTER TABLE channels ADD COLUMN is_custom BOOLEAN DEFAULT FALSE"))
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
                # Add status, approved_by, approved_at columns
                for col, col_def in (
                    ("status", "VARCHAR(20) DEFAULT 'draft'"),
                    ("approved_by", "VARCHAR(255)"),
                    ("approved_at", "DATETIME"),
                ):
                    if col not in km_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE key_messages ADD COLUMN {col} {col_def}"))
                            conn.commit()
                        except Exception:
                            pass

            # Add last_reviewed to message_houses
            if "message_houses" in insp.get_table_names():
                mh_cols = {c["name"] for c in insp.get_columns("message_houses")}
                if "last_reviewed" not in mh_cols:
                    try:
                        conn.execute(text("ALTER TABLE message_houses ADD COLUMN last_reviewed DATETIME"))
                        conn.commit()
                    except Exception:
                        pass

            # Create review_logs table
            if "review_logs" not in insp.get_table_names():
                conn.execute(text("""
                    CREATE TABLE review_logs (
                        id TEXT PRIMARY KEY,
                        house_id TEXT NOT NULL REFERENCES message_houses(id) ON DELETE CASCADE,
                        message_id TEXT,
                        action TEXT NOT NULL,
                        performed_by TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        notes TEXT DEFAULT ''
                    )
                """))
                conn.commit()

            # Add status to artifact_history if missing
            if "artifact_history" in insp.get_table_names():
                ah_cols = {c["name"] for c in insp.get_columns("artifact_history")}
                if "status" not in ah_cols:
                    try:
                        conn.execute(text("ALTER TABLE artifact_history ADD COLUMN status VARCHAR(20) DEFAULT 'draft'"))
                        conn.commit()
                    except Exception:
                        pass

            # Create source_connections table
            if "source_connections" not in insp.get_table_names():
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

            # Create source_files table
            if "source_files" not in insp.get_table_names():
                conn.execute(text("""
                    CREATE TABLE source_files (
                        id TEXT PRIMARY KEY,
                        connection_id TEXT NOT NULL REFERENCES source_connections(id) ON DELETE CASCADE,
                        drive_file_id TEXT NOT NULL,
                        file_name TEXT NOT NULL,
                        mime_type TEXT DEFAULT '',
                        house_id TEXT,
                        drive_modified_at TEXT DEFAULT '',
                        sync_status TEXT DEFAULT 'pending',
                        error_message TEXT DEFAULT '',
                        synced_at DATETIME
                    )
                """))
                conn.commit()

            # Create brand_settings table
            if "brand_settings" not in insp.get_table_names():
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

        # Create brand_assets table
        if "brand_assets" not in insp.get_table_names():
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
    ) -> None:
        with self.session() as s:
            existing = s.get(VectorMetadataModel, id)
            data = {
                "id": id,
                "message_house_id": str(message_house_id),
                "house_name": house_name,
                "house_summary": house_summary,
                "content": content,
                "section_type": section_type,
                "priority": priority,
                "persona": persona,
                "channel": channel,
                "key_message_id": str(key_message_id) if key_message_id else None,
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
                VectorMetadataModel.message_house_id == str(house_id)
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
    ) -> list[VectorMetadataModel]:
        with self.session() as s:
            query = s.query(VectorMetadataModel)
            if message_houses:
                query = query.filter(VectorMetadataModel.message_house_id.in_(message_houses))
            if section_types:
                query = query.filter(VectorMetadataModel.section_type.in_(section_types))
            if personas:
                query = query.filter(VectorMetadataModel.persona.in_(personas))
            if channels:
                query = query.filter(VectorMetadataModel.channel.in_(channels))
            if min_priority is not None:
                query = query.filter(VectorMetadataModel.priority <= min_priority)
            return query.all()

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
            channel_models = []
            if msg.channels:
                for ch in msg.channels:
                    ch_id = getattr(ch, "value", str(ch))
                    ch_model = s.get(ChannelModel, ch_id)
                    if ch_model:
                        channel_models.append(ch_model)

            existing = s.get(KeyMessageModel, str(msg.id))
            data = _to_db(msg.model_dump())
            data.pop("channels", None)

            if existing:
                for k, v in data.items():
                    if k != "id":
                        setattr(existing, k, v)
                existing.channels = channel_models
            else:
                db_msg = KeyMessageModel(**data)
                db_msg.channels = channel_models
                s.add(db_msg)
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

    # --- Review Logs ---

    def log_review_action(
        self,
        house_id: UUID,
        action: str,
        performed_by: str,
        message_id: UUID | None = None,
        notes: str = "",
    ) -> None:
        """Append a review action to the audit trail."""
        with self.session() as s:
            s.add(ReviewLogModel(
                id=str(_uuid.uuid4()),
                house_id=str(house_id),
                message_id=str(message_id) if message_id else None,
                action=action,
                performed_by=performed_by,
                timestamp=_now(),
                notes=notes,
            ))
            s.commit()

    def get_review_trail(self, house_id: UUID) -> list[dict]:
        """Return all review log entries for a house, newest first."""
        with self.session() as s:
            rows = (
                s.query(ReviewLogModel)
                .filter(ReviewLogModel.house_id == str(house_id))
                .order_by(ReviewLogModel.timestamp.desc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "house_id": r.house_id,
                    "message_id": r.message_id,
                    "action": r.action,
                    "performed_by": r.performed_by,
                    "timestamp": r.timestamp.isoformat(),
                    "notes": r.notes,
                }
                for r in rows
            ]

    def update_house_last_reviewed(self, house_id: UUID) -> None:
        """Set last_reviewed=now on a house."""
        with self.session() as s:
            row = s.get(HouseModel, str(house_id))
            if row:
                row.last_reviewed = _now()
                s.commit()


    def delete_houses_by_source_id(self, source_id: str) -> int:
        """Delete all houses with the given source_id. Returns count deleted."""
        with self.session() as s:
            rows = s.query(HouseModel).filter(HouseModel.source_id == source_id).all()
            count = len(rows)
            for row in rows:
                s.delete(row)
            if count:
                s.commit()
                _invalidate_graph()
            return count

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
                "status": row.status,
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
        from src.models import ArtifactRating
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

    def get_chunk_usage_heatmap(self, house_id: UUID) -> dict:
        """Get usage heatmap: how many times each chunk was used, with which ratings."""
        from src.models import ChunkUsageStat
        messages = self.get_key_messages(house_id)
        msg_id_to_msg = {str(m.id): m for m in messages}

        with self.session() as s:
            # Get all usage stats
            stats_rows = s.query(ChunkUsageStatModel).all()
            # Get all ratings for artifacts in this house
            artifact_rows = (
                s.query(ArtifactHistoryModel)
                .filter(ArtifactHistoryModel.house_id == str(house_id))
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
            # Check if this chunk belongs to this house
            msg = msg_id_to_msg.get(chunk_id.replace("chunk-", ""))
            if not msg and not chunk_id.startswith("chunk-"):
                msg = msg_id_to_msg.get(chunk_id)
            if not msg:
                continue
            heatmap[chunk_id] = {
                "chunk_id": chunk_id,
                "content_preview": msg.content[:100] if msg else "",
                "section_type": str(msg.section_type) if msg else "",
                "times_used": stat.times_used,
                "avg_rating": round(stat.avg_rating, 2),
                "boost_factor": round(stat.boost_factor, 2),
                "priority": msg.priority if msg else 0,
            }

        return {
            "house_id": str(house_id),
            "chunks": list(heatmap.values()),
            "total_chunks_used": len(heatmap),
            "avg_boost": round(
                sum(v["boost_factor"] for v in heatmap.values()) / max(len(heatmap), 1), 2
            ),
        }

    def get_message_house_coverage(self, house_id: UUID) -> dict:
        """Which parts of the message house are used most vs ignored."""
        messages = self.get_key_messages(house_id)
        personas = self.get_personas(house_id)

        with self.session() as s:
            stats_rows = s.query(ChunkUsageStatModel).all()

        used_chunk_ids = {s.chunk_id for s in stats_rows}
        used_times = {s.chunk_id: s.times_used for s in stats_rows}

        # Group by section type
        by_section: dict = {}
        for msg in messages:
            chunk_id = f"chunk-{msg.id}"
            st = str(msg.section_type)
            entry = by_section.setdefault(st, {"used": 0, "unused": 0, "total": 0, "times_used": 0})
            entry["total"] += 1
            if chunk_id in used_chunk_ids:
                entry["used"] += 1
                entry["times_used"] += used_times.get(chunk_id, 0)
            else:
                entry["unused"] += 1

        # Most/least used chunks
        chunk_usage = [(s.chunk_id, s.times_used) for s in stats_rows]
        chunk_usage.sort(key=lambda x: x[1], reverse=True)

        # Map chunk_id to content
        msg_map = {f"chunk-{m.id}": m.content[:80] for m in messages}

        return {
            "house_id": str(house_id),
            "by_section": by_section,
            "most_used": [
                {"chunk_id": cid, "times_used": times, "content": msg_map.get(cid, "")}
                for cid, times in chunk_usage[:10]
            ],
            "unused_chunks": [
                {"chunk_id": f"chunk-{m.id}", "content": m.content[:80], "section_type": str(m.section_type)}
                for m in messages
                if f"chunk-{m.id}" not in used_chunk_ids
            ],
            "persona_coverage": {
                p.name: {
                    "has_messages": any(p.name in (m.personas or []) for m in messages),
                    "message_count": sum(1 for m in messages if p.name in (m.personas or [])),
                }
                for p in personas
            },
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
        """Upload a brand asset (logo, icon, image) for a workspace.
        
        Args:
            workspace_id: The workspace ID
            file_path: Path to the asset file
            asset_type: Type of asset ("logo", "icon", "image")
        
        Returns:
            dict with asset info including id, asset_name, file_path
        """
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
        import os
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

    def get_channel(self, channel_id: str) -> ChannelModel | None:
        with self.session() as s:
            return s.get(ChannelModel, channel_id)

    def create_channel(self, name: str, description: str = "", is_custom: bool = True) -> ChannelModel:
        with self.session() as s:
            # Check for existing channel with the same name
            existing_by_name = s.query(ChannelModel).filter_by(name=name).first()
            if existing_by_name:
                raise ValueError(f"Channel with name '{name}' already exists.")

            channel_id = name.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
            # Ensure ID is unique
            existing_by_id = s.get(ChannelModel, channel_id)
            if existing_by_id:
                channel_id = f"{channel_id}-{uuid4().hex[:4]}" # Append a short hash if collision

            new_channel = ChannelModel(
                id=channel_id,
                name=name,
                description=description,
                is_custom=is_custom,
                created_at=_now()
            )
            s.add(new_channel)
            s.commit()
            s.refresh(new_channel)
            return new_channel

    def list_channels(self, include_custom: bool = True) -> list[ChannelModel]:
        with self.session() as s:
            q = s.query(ChannelModel)
            if not include_custom:
                q = q.filter(ChannelModel.is_custom == False)
            return q.order_by(ChannelModel.is_custom.asc(), ChannelModel.name).all()

    def update_channel(self, channel_id: str, name: str | None = None, description: str | None = None) -> ChannelModel | None:
        with self.session() as s:
            channel = s.get(ChannelModel, channel_id)
            if not channel:
                return None
            if name:
                # Check for existing channel with the same name (excluding itself)
                existing_by_name = s.query(ChannelModel).filter(
                    ChannelModel.name == name, ChannelModel.id != channel_id
                ).first()
                if existing_by_name:
                    raise ValueError(f"Channel with name '{name}' already exists.")
                channel.name = name
            if description is not None:
                channel.description = description
            s.commit()
            s.refresh(channel)
            return channel

    def delete_channel(self, channel_id: str) -> bool:
        with self.session() as s:
            channel = s.get(ChannelModel, channel_id)
            if not channel:
                return False
            if not channel.is_custom:
                raise ValueError("Cannot delete a default channel")
            s.delete(channel)
            s.commit()
            return True

    def get_channels(self) -> list[dict]:
        """Backward-compat wrapper; returns channels serialised as dicts."""
        rows = self.list_channels()
        return [{"id": r.id, "name": r.name, "description": r.description,
                 "is_custom": r.is_custom, "created_at": r.created_at.isoformat()} for r in rows]

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
        from uuid import uuid4
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
        from uuid import uuid4
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
                    row.house_id = house_id
            else:
                s.add(SourceFileModel(
                    id=str(uuid4()),
                    connection_id=connection_id,
                    drive_file_id=drive_file_id,
                    file_name=file_name,
                    mime_type=mime_type,
                    house_id=house_id,
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

    # ── Phase 1: Channel CRUD ─────────────────────────────────────────────────

    def get_channels(self) -> list[dict]:
        """Return all channels ordered: built-ins first, then custom alphabetically."""
        with self.session() as s:
            rows = s.query(ChannelModel).order_by(ChannelModel.is_custom, ChannelModel.name).all()
            return [{"id": r.id, "name": r.name, "description": r.description, "is_custom": r.is_custom} for r in rows]

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

    def get_channel_message_count(self, channel_id: str) -> int:
        """Count how many key messages are associated with a channel."""
        from sqlalchemy import select, func
        with self.session() as s:
            result = s.execute(
                select(func.count()).select_from(key_message_channel_association).where(
                    key_message_channel_association.c.channel_id == channel_id
                )
            ).scalar()
            return result or 0

    # ── Phase 3: Message Approval Workflow ────────────────────────────────────

    def update_message_status(self, message_id: str, status: str, approved_by: str = "", notes: str = "") -> dict | None:
        """Update key message status and log the action to review_logs."""
        valid = {"draft", "in_review", "approved", "outdated", "locked"}
        if status not in valid:
            raise ValueError(f"Invalid status. Must be one of: {valid}")
        with self.session() as s:
            msg = s.get(KeyMessageModel, message_id)
            if not msg:
                return None
            msg.status = status
            if status == "approved":
                msg.approved_by = approved_by or "admin"
                msg.approved_at = _now()
            log = ReviewLogModel(
                id=str(uuid4()),
                house_id=msg.message_house_id,
                message_id=message_id,
                action=status,
                performed_by=approved_by or "admin",
                timestamp=_now(),
                notes=notes,
            )
            s.add(log)
            s.commit()
            return {"id": message_id, "status": msg.status, "approved_by": msg.approved_by}

    def bulk_update_message_status(self, message_ids: list[str], status: str, approved_by: str = "") -> int:
        """Bulk update status for multiple messages. Returns count updated."""
        updated = 0
        for mid in message_ids:
            result = self.update_message_status(mid, status, approved_by)
            if result:
                updated += 1
        return updated

    def get_review_log(self, house_id: str, limit: int = 50) -> list[dict]:
        with self.session() as s:
            rows = (
                s.query(ReviewLogModel)
                .filter(ReviewLogModel.house_id == str(house_id))
                .order_by(ReviewLogModel.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "message_id": r.message_id,
                    "action": r.action,
                    "performed_by": r.performed_by,
                    "timestamp": r.timestamp.isoformat(),
                    "notes": r.notes,
                }
                for r in rows
            ]

    # ── Phase 4: Staleness / Last Reviewed ───────────────────────────────────

    def mark_house_reviewed(self, house_id: str, reviewed_by: str = "admin") -> dict | None:
        """Set last_reviewed = now() and append a review log entry."""
        with self.session() as s:
            house = s.get(HouseModel, str(house_id))
            if not house:
                return None
            house.last_reviewed = _now()
            log = ReviewLogModel(
                id=str(uuid4()),
                house_id=str(house_id),
                message_id=None,
                action="reviewed",
                performed_by=reviewed_by,
                timestamp=_now(),
                notes="Framework marked as reviewed",
            )
            s.add(log)
            s.commit()
            return {"house_id": str(house_id), "last_reviewed": house.last_reviewed.isoformat()}

    def get_stale_houses(self, days: int = 90) -> list[dict]:
        """Return houses not reviewed in the last `days` days."""
        from datetime import timedelta
        cutoff = _now() - timedelta(days=days)
        with self.session() as s:
            rows = s.query(HouseModel).filter(
                (HouseModel.last_reviewed == None) | (HouseModel.last_reviewed < cutoff)  # noqa: E711
            ).all()
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "last_reviewed": r.last_reviewed.isoformat() if r.last_reviewed else None,
                }
                for r in rows
            ]

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

    def get_message_usage_stats(self, house_id: str) -> list[dict]:
        """Return key messages with usage stats for the heatmap, sorted by times_used desc."""
        with self.session() as s:
            messages = s.query(KeyMessageModel).filter(
                KeyMessageModel.message_house_id == str(house_id)
            ).all()
            result = []
            for m in messages:
                stat = s.get(ChunkUsageStatModel, m.source_chunk_id) if m.source_chunk_id else None
                result.append({
                    "id": m.id,
                    "content": m.content,
                    "section_type": m.section_type,
                    "status": m.status,
                    "times_used": stat.times_used if stat else 0,
                    "avg_rating": round(stat.avg_rating, 1) if stat else 0.0,
                    "boost_factor": round(stat.boost_factor, 2) if stat else 1.0,
                })
            result.sort(key=lambda x: x["times_used"], reverse=True)
            return result


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
        "house_id": row.house_id,
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
        last_reviewed=row.last_reviewed,
    )


def _msg_from_row(row: KeyMessageModel) -> KeyMessage:
    from src.models import MessageStatus
    return KeyMessage(
        id=UUID(row.id),
        message_house_id=UUID(row.message_house_id),
        pillar_id=row.pillar_id,
        section_type=_safe_section_type(row.section_type),
        priority=row.priority,
        content=row.content,
        status=MessageStatus(row.status) if row.status else MessageStatus.DRAFT,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        variants=row.variants or {},
        personas=row.personas or [],
        channels=[_safe_channel(c.id if hasattr(c, "id") else str(c)) for c in (row.channels or [])] or ["all"],
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