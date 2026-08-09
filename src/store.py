"""SQLite / PostgreSQL-backed spec graph storage."""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
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
    BrandSettings, Channel, ContentTier, SchemaType, SpecStatus, AssertionStatus,
    Spec, Assertion, Audience, AssertionType,
    InheritancePolicy, ArtifactEntryBinding,
    Entity, Edge, NodeType, RelType, PROPAGATING_RELS,
    LEGACY_SECTION_TYPE_MAP, LEGACY_SCHEMA_TYPE_MAP, SchemaType,
)


log = logging.getLogger(__name__)


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
    res = {}
    for k, v in data.items():
        key = k
        res[key] = str(v) if isinstance(v, UUID) else v
    return res


class Base(DeclarativeBase):
    pass


class ArtifactEntryBindingModel(Base):
    __tablename__ = "artifact_entry_bindings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(String(36), ForeignKey("artifact_history.id", ondelete="CASCADE"), nullable=False)
    assertion_id: Mapped[str] = mapped_column(String(36), ForeignKey("assertions.id", ondelete="CASCADE"), nullable=False)
    element_type: Mapped[str] = mapped_column(String(50), nullable=False)
    bound_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EntityModel(Base):
    """A resolved concept that assertions refer to — a service, endpoint, policy,
    component. Entities are workspace-scoped rather than spec-scoped: that is what
    makes cross-spec traversal possible. Two assertions in different specs that
    mention the same service resolve to one entity node and become 2 hops apart.
    """
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="default")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # lowercase/punctuation-stripped form used for exact-match resolution
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, default="concept")
    description: Mapped[str] = mapped_column(Text, default="")
    aliases: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EntityMentionModel(Base):
    """Assertion -> Entity. The join that lets a traversal leave one spec and
    arrive in another without an explicitly authored cross-spec edge.
    """
    __tablename__ = "entity_mentions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    assertion_id: Mapped[str] = mapped_column(String(36), ForeignKey("assertions.id", ondelete="CASCADE"), nullable=False)
    spec_id: Mapped[str] = mapped_column(String(36), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EdgeModel(Base):
    """A typed, directed relationship between two graph nodes.

    src/dst are (type, id) pairs rather than foreign keys because an edge may
    connect any node kind — assertion, spec or entity — and SQLite has no
    polymorphic FK. Referential integrity is enforced on write in add_edge().
    """
    __tablename__ = "edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="default")
    src_type: Mapped[str] = mapped_column(String(20), nullable=False)   # assertion | spec | entity
    src_id: Mapped[str] = mapped_column(String(36), nullable=False)
    dst_type: Mapped[str] = mapped_column(String(20), nullable=False)
    dst_id: Mapped[str] = mapped_column(String(36), nullable=False)
    rel_type: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    provenance: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


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


class DepartmentModel(Base):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    primary_schema_type: Mapped[str] = mapped_column(String(50), nullable=False, default="engineering_spec")
    description: Mapped[str] = mapped_column(String(500), default="")
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="default")


_DEFAULT_CHANNELS = [
    ("all", "All Channels", "Universal — applies to all channels", False),
    ("email", "Email", "Email campaigns and newsletters", False),
    ("linkedin", "LinkedIn", "LinkedIn posts and sponsored content", False),
    ("twitter", "Twitter / X", "Twitter and X posts", False),
    ("paid_ads", "Paid Ads", "Display, search, and social advertising", False),
    ("landing_page", "Landing Page", "Website landing pages and hero copy", False),
    ("sales_deck", "Sales Deck", "Slide decks and pitch presentations", False),
]

# Association table for AssertionModel and ChannelModel (many-to-many)
assertion_channel_association = Table(
    "assertion_channel_association",
    Base.metadata,
    Column("assertion_id", String(36), ForeignKey("assertions.id", ondelete="CASCADE")),
    Column("channel_id", String(50), ForeignKey("channels.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("assertion_id", "channel_id")
)

# Alias for backward compatibility
key_message_channel_association = assertion_channel_association


class SpecModel(Base):
    __tablename__ = "specs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, default="default")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schema_type: Mapped[str] = mapped_column("schema_type", String(30), nullable=False, default="engineering_spec", server_default="engineering_spec")
    summary: Mapped[str] = mapped_column(Text, default="")
    audience: Mapped[str] = mapped_column(Text, default="")
    brand_personality: Mapped[str] = mapped_column(Text, default="")
    positioning: Mapped[str] = mapped_column(Text, default="")
    tagline: Mapped[str] = mapped_column(String(500), default="")
    differentiation: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    department: Mapped[str] = mapped_column(String(100), nullable=False, default="General", server_default="General")
    parent_domain_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("specs.id", ondelete="SET NULL"), nullable=True)
    inheritance_policy: Mapped[str] = mapped_column(String(50), default="full")
    last_synced: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_reviewed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dri: Mapped[str] = mapped_column(String(255), default="")

    assertions: Mapped[list["AssertionModel"]] = relationship(
        back_populates="spec", cascade="all, delete-orphan"
    )
    audiences: Mapped[list["AudienceModel"]] = relationship(
        back_populates="spec", cascade="all, delete-orphan"
    )
    pillars: Mapped[list["PillarModel"]] = relationship(
        back_populates="spec", cascade="all, delete-orphan"
    )


SpecModel = SpecModel  # Deprecated alias


class PillarModel(Base):
    __tablename__ = "pillars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    spec_id: Mapped[str] = mapped_column(String(36), ForeignKey("specs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="")
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    spec: Mapped["SpecModel"] = relationship(back_populates="pillars")


class QAPairModel(Base):
    __tablename__ = "qa_pairs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audience_id: Mapped[str] = mapped_column(String(36), ForeignKey("audiences.id", ondelete="CASCADE"), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)


class AssertionModel(Base):
    __tablename__ = "assertions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    spec_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("specs.id"), nullable=False
    )
    pillar_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("pillars.id", ondelete="SET NULL"), nullable=True)
    assertion_type: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    variants: Mapped[dict] = mapped_column(JSON, default=dict)
    audiences: Mapped[list] = mapped_column(JSON, default=list)
    # Many-to-many relationship with ChannelModel
    channels: Mapped[list["ChannelModel"]] = relationship(
        secondary=assertion_channel_association,
        backref="assertions"
    )
    source_chunk_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dri: Mapped[str] = mapped_column(String(255), default="")
    spec: Mapped["SpecModel"] = relationship(back_populates="assertions")


KeyMessageModel = AssertionModel  # Deprecated alias


class AudienceModel(Base):
    __tablename__ = "audiences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    spec_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("specs.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="")
    qa_pairs: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    spec: Mapped["SpecModel"] = relationship(back_populates="audiences")


class SnapshotModel(Base):
    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    spec_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("specs.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), default="")
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ArtifactHistoryModel(Base):
    __tablename__ = "artifact_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    spec_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("specs.id"), nullable=False
    )
    skill_id: Mapped[str] = mapped_column(String(100), nullable=False)
    spec_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sections_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    alignment_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    spec_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
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
    spec_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("specs.id", ondelete="CASCADE"), nullable=False
    )
    assertion_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    performed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")


    @property
    def message_id(self) -> str | None:
        return self.assertion_id
    @message_id.setter
    def message_id(self, val: str | None) -> None:
        self.assertion_id = val


class VectorMetadataModel(Base):
    __tablename__ = "vector_metadata"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # e.g., 'chunk-UUID', 'field-UUID-field', 'kym-UUID'
    spec_id: Mapped[str] = mapped_column(String(36), nullable=False)
    spec_name: Mapped[str] = mapped_column(String(255), nullable=False)
    spec_summary: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    assertion_type: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    audience: Mapped[str] = mapped_column(String(255), default="general")
    channel: Mapped[str] = mapped_column(String(255), default="all")
    assertion_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_synced: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    content_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)


# Performance indexes on high-cardinality FK / filter columns
Index("ix_km_spec_id", AssertionModel.spec_id)
Index("ix_km_pillar_id", AssertionModel.pillar_id)
Index("ix_audience_spec_id", AudienceModel.spec_id)
Index("ix_snapshot_spec_id", SnapshotModel.spec_id)
Index("ix_artifact_spec_id", ArtifactHistoryModel.spec_id)
Index("ix_token_usage_workspace", TokenUsageModel.workspace_id)
Index("ix_api_key_workspace", ApiKeyModel.workspace_id)
Index("ix_spec_workspace", SpecModel.workspace_id)
Index("ix_pillar_spec_id", PillarModel.spec_id)
Index("ix_source_files_conn", SourceFileModel.connection_id)
Index("ix_source_files_drive_id", SourceFileModel.drive_file_id)
Index("ix_review_logs_spec_id", ReviewLogModel.spec_id)
Index("ix_review_logs_timestamp", ReviewLogModel.timestamp)
Index("ix_artifact_rating_artifact_id", ArtifactRatingModel.artifact_id)
Index("ix_chunk_usage_chunk_id", ChunkUsageStatModel.chunk_id)
Index("ix_vector_metadata_spec_id", VectorMetadataModel.spec_id)
Index("ix_binding_artifact", ArtifactEntryBindingModel.artifact_id)
Index("ix_binding_entry", ArtifactEntryBindingModel.assertion_id)
Index("ix_entity_norm", EntityModel.workspace_id, EntityModel.normalized_name)
Index("ix_mention_entity", EntityMentionModel.entity_id)
Index("ix_mention_assertion", EntityMentionModel.assertion_id)
Index("ix_edge_src", EdgeModel.src_type, EdgeModel.src_id)
Index("ix_edge_dst", EdgeModel.dst_type, EdgeModel.dst_id)
Index("ix_edge_rel", EdgeModel.rel_type)


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
        self._seed_default_departments()

    def _migrate(self) -> None:
        """Apply table renames, column renames, and additive migrations for columns."""
        from sqlalchemy import text, inspect
        insp = inspect(self.engine)
        tables = insp.get_table_names()
        with self.engine.connect() as conn:
            # ── Historical schema migration ──────────────────────────────
            # The string literals below are deliberately NOT the current
            # vocabulary — they are the on-disk names of earlier generations
            # that this code exists to migrate away from. Do not "fix" them
            # to match the current models; a bulk rename over this block
            # silently turns every step into a no-op.
            #
            #   gen-0  message_house era   (message_houses / key_messages)
            #   gen-1  canon era           (canon_domains / canon_entries)
            #   gen-2  spec era            (specs / assertions)   <- current

            def _rename_tables(pairs):
                nonlocal insp, tables
                for old, new_name in pairs:
                    if old in tables and new_name not in tables:
                        conn.execute(text(f"ALTER TABLE {old} RENAME TO {new_name}"))
                        conn.commit()
                insp = inspect(self.engine)
                tables = insp.get_table_names()

            def _rename_columns(triples):
                for tbl, old, new_col in triples:
                    if tbl not in tables:
                        continue
                    cols = {c["name"] for c in insp.get_columns(tbl)}
                    if old in cols and new_col not in cols:
                        conn.execute(text(
                            f"ALTER TABLE {tbl} RENAME COLUMN {old} TO {new_col}"))
                        conn.commit()

            _rename_tables([
                ('message_houses', 'canon_domains'),
                ('key_messages', 'canon_entries'),
                ('key_message_channel_association', 'canon_entry_channel_association'),
            ])
            _rename_columns([
                ('canon_entries', 'message_house_id', 'canon_domain_id'),
                ('personas', 'message_house_id', 'canon_domain_id'),
                ('pillars', 'house_id', 'canon_domain_id'),
                ('snapshots', 'house_id', 'canon_domain_id'),
                ('artifact_history', 'house_id', 'canon_domain_id'),
                ('review_logs', 'house_id', 'canon_domain_id'),
                ('review_logs', 'message_id', 'canon_entry_id'),
                ('vector_metadata', 'message_house_id', 'canon_domain_id'),
                ('vector_metadata', 'key_message_id', 'canon_entry_id'),
                ('vector_metadata', 'house_name', 'canon_domain_name'),
                ('vector_metadata', 'house_summary', 'canon_domain_summary'),
                ('canon_entry_channel_association', 'key_message_id', 'canon_entry_id'),
                ('source_files', 'house_id', 'canon_domain_id'),
            ])
            _rename_tables([
                ('canon_domains', 'specs'),
                ('canon_entries', 'assertions'),
                ('canon_entry_channel_association', 'assertion_channel_association'),
            ])
            _rename_columns([
                ('assertions', 'canon_domain_id', 'spec_id'),
                ('personas', 'canon_domain_id', 'spec_id'),
                ('audiences', 'canon_domain_id', 'spec_id'),
                ('pillars', 'canon_domain_id', 'spec_id'),
                ('snapshots', 'canon_domain_id', 'spec_id'),
                ('artifact_history', 'canon_domain_id', 'spec_id'),
                ('review_logs', 'canon_domain_id', 'spec_id'),
                ('review_logs', 'canon_entry_id', 'assertion_id'),
                ('vector_metadata', 'canon_domain_id', 'spec_id'),
                ('vector_metadata', 'canon_entry_id', 'assertion_id'),
                ('vector_metadata', 'canon_domain_name', 'spec_name'),
                ('vector_metadata', 'canon_domain_summary', 'spec_summary'),
                ('assertion_channel_association', 'canon_entry_id', 'assertion_id'),
                ('source_files', 'canon_domain_id', 'spec_id'),
                ('artifact_entry_bindings', 'canon_entry_id', 'assertion_id'),
            ])
            insp = inspect(self.engine)
            tables = insp.get_table_names()

            # ── Generation 2 → 3: PMM schema → engineering schema ────────
            _rename_tables([
                ('personas', 'audiences'),
                ('objections', 'qa_pairs'),
            ])
            _rename_columns([
                ('assertions', 'section_type', 'assertion_type'),
                ('vector_metadata', 'section_type', 'assertion_type'),
                ('assertions', 'persona_ids', 'audience_ids'),
                ('assertions', 'personas', 'audiences'),
                ('vector_metadata', 'persona', 'audience'),
                ('qa_pairs', 'persona_id', 'audience_id'),
                ('audiences', 'persona_id', 'audience_id'),
                ('audiences', 'canon_domain_id', 'spec_id'),
                ('audiences', 'objections', 'qa_pairs'),
                ('specs', 'document_type', 'schema_type'),
                ('departments', 'primary_grounding_type', 'primary_schema_type'),
            ])

            # Map legacy section_type values onto AssertionType. Unmappable
            # values become 'capability' rather than being dropped — a
            # mis-typed fact is recoverable, a deleted one is not.
            insp = inspect(self.engine)
            tables = insp.get_table_names()
            if "assertions" in tables:
                cols = {c["name"] for c in insp.get_columns("assertions")}
                col = "assertion_type" if "assertion_type" in cols else "section_type"
                if col in cols:
                    known = {r[0] for r in conn.execute(text(
                        f"SELECT DISTINCT {col} FROM assertions"))}
                    valid = {t.value for t in AssertionType}
                    for old_val in known:
                        if old_val in valid or old_val is None:
                            continue
                        new_val = LEGACY_SECTION_TYPE_MAP.get(
                            old_val, AssertionType.CAPABILITY.value)
                        conn.execute(
                            text(f"UPDATE assertions SET {col} = :new WHERE {col} = :old"),
                            {"new": new_val, "old": old_val})
                        if old_val not in LEGACY_SECTION_TYPE_MAP:
                            log.warning(
                                "Unmapped legacy section_type %r -> %r; review these rows",
                                old_val, new_val)
                    conn.commit()

            # Same treatment for schema_type: existing rows carry PMM-era
            # values (message_house, persona_library, …) that are no longer
            # members of the enum, and Pydantic rejects them on read.
            if "specs" in tables:
                cols = {c["name"] for c in insp.get_columns("specs")}
                col = "schema_type" if "schema_type" in cols else "document_type"
                if col in cols:
                    known = {r[0] for r in conn.execute(text(
                        f"SELECT DISTINCT {col} FROM specs"))}
                    valid = {t.value for t in SchemaType}
                    for old_val in known:
                        if old_val in valid or old_val is None:
                            continue
                        new_val = LEGACY_SCHEMA_TYPE_MAP.get(
                            old_val, SchemaType.ENGINEERING_SPEC.value)
                        conn.execute(
                            text(f"UPDATE specs SET {col} = :new WHERE {col} = :old"),
                            {"new": new_val, "old": old_val})
                        if old_val not in LEGACY_SCHEMA_TYPE_MAP:
                            log.warning(
                                "Unmapped legacy schema_type %r -> %r", old_val, new_val)
                    conn.commit()

            # PMM child tables. Their rows were exported to
            # data/archive/pmm-export-2026-08-07.json before this ran.
            for dead in ("pain_points", "buying_triggers"):
                if dead in tables:
                    conn.execute(text(f"DROP TABLE {dead}"))
                    conn.commit()

            insp = inspect(self.engine)
            tables = insp.get_table_names()

            # 3. Additive migrations
            if "specs" in tables:
                mh_cols = {c["name"] for c in insp.get_columns("specs")}
                if "schema_type" not in mh_cols:
                    conn.execute(text(
                        "ALTER TABLE specs ADD COLUMN schema_type VARCHAR(30) "
                        "NOT NULL DEFAULT 'engineering_spec'"
                    ))
                    conn.commit()
                if "last_reviewed" not in mh_cols:
                    try:
                        conn.execute(text("ALTER TABLE specs ADD COLUMN last_reviewed DATETIME"))
                        conn.commit()
                    except Exception:
                        pass
                if "department" not in mh_cols:
                    try:
                        conn.execute(text(
                            "ALTER TABLE specs ADD COLUMN department VARCHAR(100) "
                            "NOT NULL DEFAULT 'General'"
                        ))
                        conn.commit()
                    except Exception:
                        pass
                if "parent_domain_id" not in mh_cols:
                    try:
                        conn.execute(text("ALTER TABLE specs ADD COLUMN parent_domain_id VARCHAR(36) REFERENCES specs(id) ON DELETE SET NULL"))
                        conn.commit()
                    except Exception:
                        pass
                if "inheritance_policy" not in mh_cols:
                    try:
                        conn.execute(text("ALTER TABLE specs ADD COLUMN inheritance_policy VARCHAR(50) DEFAULT 'full'"))
                        conn.commit()
                    except Exception:
                        pass
                if "dri" not in mh_cols:
                    try:
                        conn.execute(text("ALTER TABLE specs ADD COLUMN dri VARCHAR(255) DEFAULT ''"))
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
                        spec_id VARCHAR(36) NOT NULL REFERENCES specs(id) ON DELETE CASCADE,
                        name TEXT NOT NULL,
                        description TEXT,
                        display_order INTEGER DEFAULT 0
                    )
                """))
                conn.commit()

            if "assertions" in tables:
                km_cols = {c["name"] for c in insp.get_columns("assertions")}
                if "pillar_id" not in km_cols:
                    try:
                        conn.execute(text("ALTER TABLE assertions ADD COLUMN pillar_id INTEGER REFERENCES pillars(id) ON DELETE SET NULL"))
                        conn.commit()
                    except Exception:
                        pass
                if "content_tier" not in km_cols:
                    try:
                        conn.execute(text("ALTER TABLE assertions ADD COLUMN content_tier VARCHAR(20) DEFAULT NULL"))
                        conn.commit()
                    except Exception:
                        pass
                if "dri" not in km_cols:
                    try:
                        conn.execute(text("ALTER TABLE assertions ADD COLUMN dri VARCHAR(255) DEFAULT ''"))
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
                            conn.execute(text(f"ALTER TABLE assertions ADD COLUMN {col} {col_def}"))
                            conn.commit()
                        except Exception:
                            pass

            if "qa_pairs" not in tables:
                conn.execute(text("""
                    CREATE TABLE qa_pairs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        audience_id TEXT NOT NULL REFERENCES audiences(id) ON DELETE CASCADE,
                        statement TEXT NOT NULL,
                        response TEXT
                    )
                """))
                conn.commit()

            if "review_logs" not in tables:
                conn.execute(text("""
                    CREATE TABLE review_logs (
                        id TEXT PRIMARY KEY,
                        spec_id TEXT NOT NULL REFERENCES specs(id) ON DELETE CASCADE,
                        assertion_id TEXT,
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
            if "entities" not in tables:
                conn.execute(text("""
                    CREATE TABLE entities (
                        id VARCHAR(36) PRIMARY KEY,
                        workspace_id VARCHAR(36) NOT NULL DEFAULT 'default',
                        name VARCHAR(255) NOT NULL,
                        normalized_name VARCHAR(255) NOT NULL,
                        entity_type VARCHAR(50) NOT NULL DEFAULT 'concept',
                        description TEXT DEFAULT '',
                        aliases TEXT DEFAULT '[]',
                        created_at DATETIME NOT NULL
                    )
                """))
                conn.commit()

            if "entity_mentions" not in tables:
                conn.execute(text("""
                    CREATE TABLE entity_mentions (
                        id VARCHAR(36) PRIMARY KEY,
                        entity_id VARCHAR(36) NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                        assertion_id VARCHAR(36) NOT NULL REFERENCES assertions(id) ON DELETE CASCADE,
                        spec_id VARCHAR(36) NOT NULL,
                        confidence FLOAT DEFAULT 1.0,
                        created_at DATETIME NOT NULL
                    )
                """))
                conn.commit()

            if "edges" not in tables:
                conn.execute(text("""
                    CREATE TABLE edges (
                        id VARCHAR(36) PRIMARY KEY,
                        workspace_id VARCHAR(36) NOT NULL DEFAULT 'default',
                        src_type VARCHAR(20) NOT NULL,
                        src_id VARCHAR(36) NOT NULL,
                        dst_type VARCHAR(20) NOT NULL,
                        dst_id VARCHAR(36) NOT NULL,
                        rel_type VARCHAR(30) NOT NULL,
                        confidence FLOAT DEFAULT 1.0,
                        provenance TEXT DEFAULT '',
                        created_by VARCHAR(255) DEFAULT '',
                        created_at DATETIME NOT NULL
                    )
                """))
                conn.commit()

            if "brand_assets" in tables:
                ba_cols = {c["name"] for c in insp.get_columns("brand_assets")}
                for col, col_def in (
                    ("mime_type", "VARCHAR(100) DEFAULT ''"),
                    ("file_size", "INTEGER DEFAULT 0"),
                    ("updated_at", "DATETIME"),
                ):
                    if col not in ba_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE brand_assets ADD COLUMN {col} {col_def}"))
                            conn.commit()
                        except Exception:
                            pass

            if "artifact_entry_bindings" not in tables:
                conn.execute(text("""
                    CREATE TABLE artifact_entry_bindings (
                        id VARCHAR(36) PRIMARY KEY,
                        artifact_id VARCHAR(36) NOT NULL REFERENCES artifact_history(id) ON DELETE CASCADE,
                        assertion_id VARCHAR(36) NOT NULL REFERENCES assertions(id) ON DELETE CASCADE,
                        element_type VARCHAR(50) NOT NULL,
                        bound_text TEXT,
                        created_at DATETIME NOT NULL
                    )
                """))
                conn.commit()

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
                        spec_id TEXT,
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
                        mime_type VARCHAR(100) DEFAULT '',
                        file_size INTEGER DEFAULT 0,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME
                    )
                """))
                conn.commit()

            if "audiences" in tables:
                p_cols = {c["name"] for c in insp.get_columns("audiences")}
                for col, col_def in (
                    ("status", "VARCHAR(20) DEFAULT 'draft'"),
                    ("approved_by", "VARCHAR(255)"),
                    ("approved_at", "DATETIME"),
                ):
                    if col not in p_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE audiences ADD COLUMN {col} {col_def}"))
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

    def _seed_default_departments(self) -> None:
        defaults = [
            ("General", "engineering_spec", "Uncategorised specs"),
            ("Engineering", "engineering_spec", "Services, APIs, interface contracts, and their constraints"),
            ("Platform", "service_catalog", "Service inventory, dependencies, and ownership"),
            ("Security", "policy_shield", "Security posture, compliance assertions, and approved responses"),
            ("Operations", "incident_record", "Runbooks, postmortems, and operational decisions"),
        ]
        with self.session() as s:
            for name, g_type, desc in defaults:
                exists = s.get(DepartmentModel, name)
                if not exists:
                    s.add(DepartmentModel(name=name, primary_schema_type=g_type, description=desc, workspace_id="default"))
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
        spec_id: UUID,
        spec_name: str,
        spec_summary: str,
        content: str,
        assertion_type: str,
        priority: int,
        audience: str,
        channel: str,
        assertion_id: Optional[UUID] = None,
        last_synced: Optional[datetime] = None,
        content_tier: Optional[str] = None,
    ) -> None:
        with self.session() as s:
            existing = s.get(VectorMetadataModel, id)
            data = {
                "id": id,
                "spec_id": str(spec_id),
                "spec_name": spec_name,
                "spec_summary": spec_summary,
                "content": content,
                "assertion_type": assertion_type,
                "priority": priority,
                "audience": audience,
                "channel": channel,
                "assertion_id": str(assertion_id) if assertion_id else None,
                "last_synced": last_synced,
                "content_tier": content_tier,
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

    def delete_vector_metadata_for_spec(self, spec_id: UUID) -> int:
        with self.session() as s:
            deleted = s.query(VectorMetadataModel).filter(
                VectorMetadataModel.spec_id == str(spec_id)
            ).delete()
            s.commit()
            return deleted

    def list_vector_metadata_matching_filters(
        self,
        specs: Optional[list[str]] = None,
        assertion_types: Optional[list[str]] = None,
        audiences: Optional[list[str]] = None,
        channels: Optional[list[str]] = None,
        min_priority: Optional[int] = None,
    ) -> list[VectorMetadataModel]:
        with self.session() as s:
            query = s.query(VectorMetadataModel)
            if specs:
                query = query.filter(VectorMetadataModel.spec_id.in_(specs))
            if assertion_types:
                query = query.filter(VectorMetadataModel.assertion_type.in_(assertion_types))
            if audiences:
                query = query.filter(VectorMetadataModel.audience.in_(audiences))
            if channels:
                query = query.filter(VectorMetadataModel.channel.in_(channels))
            if min_priority is not None:
                query = query.filter(VectorMetadataModel.priority <= min_priority)
            return query.all()

    def upsert_spec(self, domain: Spec, workspace_id: str = "default") -> None:
        with self.session() as s:
            existing = s.get(SpecModel, str(domain.id))
            if existing:
                for k, v in _to_db(domain.model_dump()).items():
                    if k != "id":
                        setattr(existing, k, v)
            else:
                data = _to_db(domain.model_dump())
                data["workspace_id"] = workspace_id
                s.add(SpecModel(**data))
            s.commit()
        _invalidate_graph()

    upsert_spec = upsert_spec  # Deprecated alias

    def get_spec(self, domain_id: UUID) -> Spec | None:
        with self.session() as s:
            row = s.get(SpecModel, str(domain_id))
            if not row:
                return None
            return _domain_from_row(row)

    get_spec = get_spec  # Deprecated alias

    def get_spec_workspace_id(self, domain_id: UUID) -> str | None:
        with self.session() as s:
            row = s.get(SpecModel, str(domain_id))
            return row.workspace_id if row else None

    def get_spec_by_name(self, name: str) -> Spec | None:
        with self.session() as s:
            # 1. Try exact match first
            row = s.query(SpecModel).filter(SpecModel.name == name).first()
            # 2. Try case-insensitive exact match
            if not row:
                row = s.query(SpecModel).filter(SpecModel.name.ilike(name)).first()
            # 3. Try partial substring match (case-insensitive)
            if not row:
                row = s.query(SpecModel).filter(SpecModel.name.ilike(f"%{name}%")).first()
            
            if not row:
                return None
            return _domain_from_row(row)

    get_spec_by_name = get_spec_by_name  # Deprecated alias

    def upsert_assertion(self, entry: Assertion) -> None:
        with self.session() as s:
            channel_models = []
            if entry.channels:
                for ch in entry.channels:
                    ch_id = getattr(ch, "value", str(ch))
                    ch_model = s.get(ChannelModel, ch_id)
                    if ch_model:
                        channel_models.append(ch_model)

            existing = s.get(AssertionModel, str(entry.id))
            data = _to_db(entry.model_dump())
            data.pop("channels", None)

            # Check if content actually changed to avoid false triggers
            content_changed = False
            if existing and existing.content != entry.content:
                content_changed = True

            if existing:
                for k, v in data.items():
                    if k != "id":
                        setattr(existing, k, v)
                existing.channels = channel_models
            else:
                db_entry = AssertionModel(**data)
                db_entry.channels = channel_models
                s.add(db_entry)
            
            s.commit()

            # Active Binding Propagation Trigger
            if content_changed:
                bindings = s.query(ArtifactEntryBindingModel).filter(
                    ArtifactEntryBindingModel.assertion_id == str(entry.id)
                ).all()
                for b in bindings:
                    # Log review trace
                    log_model = ReviewLogModel(
                        id=str(uuid4()),
                        spec_id=str(entry.spec_id),
                        assertion_id=str(entry.id),
                        action="propagation_drift",
                        performed_by="system_bindings",
                        timestamp=datetime.now(),
                        notes=f"Deliverable {b.artifact_id} flags drift due to update in assertion {entry.id}."
                    )
                    s.add(log_model)
                    
                    # Flag downstream artifact stale
                    art = s.get(ArtifactHistoryModel, b.artifact_id)
                    if art:
                        art.status = "draft"  # Set to draft so it requires re-approval/review
                s.commit()

        if content_changed:
            self.propagate_change("assertion", str(entry.id))

        _invalidate_graph()

    upsert_key_message = upsert_assertion  # Deprecated alias

    def get_assertions(self, domain_id: UUID, include_unapproved: bool = False) -> list[Assertion]:
        # 1. Fetch target child domain to check inheritance policy
        domain = self.get_spec(domain_id)
        if not domain:
            return []

        policy = domain.inheritance_policy or "full"

        # 2. Base query: fetch entries directly in this child domain
        with self.session() as s:
            query = s.query(AssertionModel).filter(AssertionModel.spec_id == str(domain_id))
            if not include_unapproved:
                query = query.filter(AssertionModel.status.in_(["approved", "locked"]))
            child_rows = query.order_by(AssertionModel.priority).all()
            child_entries = [_entry_from_row(r) for r in child_rows]

        # If policy is autonomous, do not fetch parents
        if policy == "autonomous" or not domain.parent_domain_id:
            return child_entries

        # 3. Recursively fetch parent entries
        parent_entries = self.get_assertions(domain.parent_domain_id, include_unapproved=include_unapproved)

        # 4. Merge based on policy type
        if policy == "full":
            # Direct union
            return child_entries + parent_entries

        elif policy == "selective_override":
            # Child entries override parent entries of the exact same section type
            child_assertion_types = {e.assertion_type for e in child_entries}
            filtered_parents = [e for e in parent_entries if e.assertion_type not in child_assertion_types]
            return child_entries + filtered_parents

        elif policy == "vocab_constrained":
            # Fetch parents and filter child entries by parent's word list constraints (if any)
            # Find parent "word_list" entries representing banned terms or owned terms
            banned_terms = []
            for pe in parent_entries:
                if pe.assertion_type == "word_list" and "banned" in pe.content.lower():
                    # Parse out words
                    banned_terms.extend([word.strip().lower() for word in pe.content.split(",") if word.strip()])

            filtered_child = []
            for ce in child_entries:
                # Check for banned words in content
                content_lower = ce.content.lower()
                has_banned = any(term in content_lower for term in banned_terms)
                if not has_banned:
                    filtered_child.append(ce)
                else:
                    # Log or flag warning (for now we filter/skip)
                    pass

            return filtered_child + parent_entries

        return child_entries

    get_key_messages = get_assertions  # Deprecated alias

    def get_assertion(self, entry_id: UUID) -> Assertion | None:
        with self.session() as s:
            row = s.get(AssertionModel, str(entry_id))
            return _entry_from_row(row) if row else None

    get_key_message = get_assertion  # Deprecated alias

    def get_audience(self, audience_id: UUID) -> Audience | None:
        with self.session() as s:
            row = s.get(AudienceModel, str(audience_id))
            return _audience_from_row(row) if row else None

    def upsert_audience(self, audience: Audience) -> None:
        with self.session() as s:
            existing = s.get(AudienceModel, str(audience.id))
            if existing:
                for k, v in _to_db(audience.model_dump()).items():
                    if k != "id":
                        setattr(existing, k, v)
            else:
                s.add(AudienceModel(**_to_db(audience.model_dump())))
            s.commit()
        _invalidate_graph()

    def get_audiences(self, domain_id: UUID) -> list[Audience]:
        domain = self.get_spec(domain_id)
        if not domain:
            return []
        
        with self.session() as s:
            rows = s.query(AudienceModel).filter(AudienceModel.spec_id == str(domain_id)).all()
            child_audiences = [_audience_from_row(r) for r in rows]

        if not domain.parent_domain_id or domain.inheritance_policy == "autonomous":
            return child_audiences

        # Inherit parent audiences
        parent_audiences = self.get_audiences(domain.parent_domain_id)
        
        # Merge by audience name (child overrides parent of same name)
        child_names = {p.name for p in child_audiences}
        filtered_parents = [p for p in parent_audiences if p.name not in child_names]
        
        return child_audiences + filtered_parents

    def get_audience_by_name(self, domain_id: UUID, name: str) -> Audience | None:
        with self.session() as s:
            row = (
                s.query(AudienceModel)
                .filter(AudienceModel.spec_id == str(domain_id), AudienceModel.name == name)
                .first()
            )
            return _audience_from_row(row) if row else None

    def bulk_create_qa_pairs(self, audience_id: str, items: list[dict]) -> list[int]:
        with self.session() as s:
            new_ids = []
            for ob in items:
                stmt = ob.get("statement", "")
                resp = ob.get("response")
                obj = QAPairModel(audience_id=audience_id, statement=stmt, response=resp)
                s.add(obj)
                s.flush()
                new_ids.append(obj.id)
            s.commit()
            return new_ids

    def delete_audience_sub_attrs(self, audience_id: str) -> None:
        with self.session() as s:
            s.query(QAPairModel).filter(QAPairModel.audience_id == audience_id).delete()
            s.commit()

    def list_qa_pairs(self, audience_id: str) -> list:
        with self.session() as s:
            return s.query(QAPairModel).filter(QAPairModel.audience_id == audience_id).all()

    def delete_spec(self, domain_id: UUID) -> bool:
        with self.session() as s:
            row = s.get(SpecModel, str(domain_id))
            if row:
                s.delete(row)
                s.commit()
                _invalidate_graph()
                return True
            return False

    delete_spec = delete_spec  # Deprecated alias

    # --- Review Logs ---

    def log_review_action(
        self,
        domain_id: Optional[UUID] = None,
        action: str = "",
        performed_by: str = "",
        entry_id: Optional[UUID] = None,
        notes: str = "",
        # Compatibility arguments
        spec_id: Optional[UUID] = None,
        message_id: Optional[UUID] = None,
    ) -> None:
        """Append a review action to the audit trail."""
        actual_domain_id = domain_id or spec_id
        actual_entry_id = entry_id or message_id
        with self.session() as s:
            s.add(ReviewLogModel(
                id=str(_uuid.uuid4()),
                spec_id=str(actual_domain_id),
                assertion_id=str(actual_entry_id) if actual_entry_id else None,
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
                .filter(ReviewLogModel.spec_id == str(domain_id))
                .order_by(ReviewLogModel.timestamp.desc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "domain_id": r.spec_id,
                    "spec_id": r.spec_id,
                    "entry_id": r.assertion_id,
                    "message_id": r.assertion_id,
                    "action": r.action,
                    "performed_by": r.performed_by,
                    "timestamp": r.timestamp.isoformat(),
                    "notes": r.notes,
                }
                for r in rows
            ]

    def get_entry_review_trail(self, entry_id: str) -> list[dict]:
        """Return all review log entries for a specific assertion, newest first."""
        with self.session() as s:
            rows = (
                s.query(ReviewLogModel)
                .filter(ReviewLogModel.assertion_id == entry_id)
                .order_by(ReviewLogModel.timestamp.desc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "domain_id": r.spec_id,
                    "spec_id": r.spec_id,
                    "entry_id": r.assertion_id,
                    "message_id": r.assertion_id,
                    "action": r.action,
                    "performed_by": r.performed_by,
                    "timestamp": r.timestamp.isoformat(),
                    "notes": r.notes,
                }
                for r in rows
            ]

    get_message_review_trail = get_entry_review_trail  # Deprecated alias

    def update_spec_last_reviewed(self, domain_id: UUID) -> None:
        """Set last_reviewed=now on a domain."""
        with self.session() as s:
            row = s.get(SpecModel, str(domain_id))
            if row:
                row.last_reviewed = _now()
                s.commit()

    def delete_specs_by_source_id(self, source_id: str) -> int:
        """Delete all domains with the given source_id. Returns count deleted."""
        with self.session() as s:
            rows = s.query(SpecModel).filter(SpecModel.source_id == source_id).all()
            count = len(rows)
            for row in rows:
                s.delete(row)
            if count:
                s.commit()
                _invalidate_graph()
            return count

    delete_specs_by_source_id = delete_specs_by_source_id  # Deprecated alias

    def delete_assertion(self, entry_id: UUID) -> bool:
        with self.session() as s:
            row = s.get(AssertionModel, str(entry_id))
            if row:
                s.delete(row)
                s.commit()
                _invalidate_graph()
                return True
            return False

    delete_key_message = delete_assertion  # Deprecated alias

    def delete_audience(self, audience_id: UUID) -> bool:
        with self.session() as s:
            row = s.get(AudienceModel, str(audience_id))
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
                spec_id=str(domain_id),
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
                .filter(PillarModel.spec_id == str(domain_id))
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
        """Delete pillar; SET NULL cascades to assertions. Returns True if found."""
        with self.session() as s:
            row = s.get(PillarModel, pillar_id)
            if not row:
                return False
            s.delete(row)
            s.commit()
            _invalidate_graph()
            return True

    def assign_chunk_to_pillar(self, chunk_id: UUID, pillar_id: int | None) -> bool:
        """Set assertions.pillar_id. Pass None to unassign."""
        with self.session() as s:
            row = s.get(AssertionModel, str(chunk_id))
            if not row:
                return False
            row.pillar_id = pillar_id
            s.commit()
            _invalidate_graph()
            return True

    # --- Snapshots ---

    def create_snapshot(self, domain_id: UUID, label: str = "") -> dict:
        domain = self.get_spec(domain_id)
        if not domain:
            raise ValueError(f"Domain {domain_id} not found")
        entries = self.get_assertions(domain_id, include_unapproved=True)
        audiences = self.get_audiences(domain_id)
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
                "department": domain.department,
            },
            # Compatibility key:
            "spec": {
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
                "department": domain.department,
            },
            "entries": [
                {
                    "id": str(e.id),
                    "assertion_type": str(e.assertion_type),
                    "priority": e.priority,
                    "content": e.content,
                    "variants": e.variants,
                    "audiences": e.audiences,
                    "channels": [str(c) for c in e.channels],
                }
                for e in entries
            ],
            # Compatibility key:
            "messages": [
                {
                    "id": str(e.id),
                    "assertion_type": str(e.assertion_type),
                    "priority": e.priority,
                    "content": e.content,
                    "variants": e.variants,
                    "audiences": e.audiences,
                    "channels": [str(c) for c in e.channels],
                }
                for e in entries
            ],
            "audiences": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "description": p.description,
                    "qa_pairs": p.qa_pairs,
                }
                for p in audiences
            ],
        }
        snap_id = str(uuid4())
        now = _now()
        with self.session() as s:
            s.add(SnapshotModel(
                id=snap_id,
                spec_id=str(domain_id),
                label=label or f"Snapshot {now.strftime('%Y-%m-%d %H:%M')}",
                snapshot_json=snapshot_data,
                created_at=now,
            ))
            s.commit()
        return {"id": snap_id, "domain_id": str(domain_id), "spec_id": str(domain_id), "label": label, "created_at": now.isoformat()}

    def list_snapshots(self, domain_id: UUID) -> list[dict]:
        with self.session() as s:
            rows = (
                s.query(SnapshotModel)
                .filter(SnapshotModel.spec_id == str(domain_id))
                .order_by(SnapshotModel.created_at.desc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "domain_id": r.spec_id,
                    "spec_id": r.spec_id,
                    "label": r.label,
                    "created_at": r.created_at.isoformat(),
                    "entry_count": len(r.snapshot_json.get("entries", [])),
                    "message_count": len(r.snapshot_json.get("messages", [])),
                    "audience_count": len(r.snapshot_json.get("audiences", [])),
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
                "domain_id": row.spec_id,
                "spec_id": row.spec_id,
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
        domain_id = UUID(snap_data.get("domain", snap_data.get("spec"))["id"])

        current_domain = self.get_spec(domain_id)
        if not current_domain:
            raise ValueError("Domain no longer exists")

        current_entries = self.get_assertions(domain_id, include_unapproved=True)
        current_audiences = self.get_audiences(domain_id)

        field_changes = {}
        snap_domain = snap_data.get("domain", snap_data.get("spec"))
        for field in ("name", "summary", "audience", "brand_personality", "positioning", "tagline", "differentiation"):
            snap_val = snap_domain.get(field, "")
            curr_val = getattr(current_domain, field, "") or ""
            if snap_val != curr_val:
                field_changes[field] = {"snapshot": snap_val, "current": curr_val}

        snap_entries = {e["id"]: e for e in snap_data.get("entries", snap_data.get("messages", []))}
        curr_entries = {str(e.id): e for e in current_entries}

        added_entries = [
            {"id": eid, "content": e.content, "assertion_type": str(e.assertion_type)}
            for eid, e in curr_entries.items() if eid not in snap_entries
        ]
        removed_entries = [
            {"id": eid, "content": e["content"], "assertion_type": e["assertion_type"]}
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
                        "assertion_type": str(curr_e.assertion_type),
                    })

        snap_audiences = {p["id"]: p for p in snap_data.get("audiences", [])}
        curr_audiences = {str(p.id): p for p in current_audiences}
        added_audiences = [{"id": pid, "name": p.name} for pid, p in curr_audiences.items() if pid not in snap_audiences]
        removed_audiences = [{"id": pid, "name": p["name"]} for pid, p in snap_audiences.items() if pid not in curr_audiences]

        return {
            "snapshot_id": str(snapshot_id),
            "snapshot_label": snap["label"],
            "snapshot_created_at": snap["created_at"],
            "domain_id": str(domain_id),
            "spec_id": str(domain_id),
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
            "audiences": {
                "added": added_audiences,
                "removed": removed_audiences,
            },
            "has_changes": bool(field_changes or added_entries or removed_entries or changed_entries or added_audiences or removed_audiences),
        }

    # --- Artifact History ---

    def save_artifact(self, spec_id: UUID, skill_id: str, spec_name: str,
                       sections: dict, raw_content: str = "", alignment_score: int | None = None) -> dict:
        art_id = str(uuid4())
        now = _now()
        with self.session() as s:
            s.add(ArtifactHistoryModel(
                id=art_id,
                spec_id=str(spec_id),
                skill_id=skill_id,
                spec_name=spec_name,
                sections_json=sections,
                raw_content=raw_content,
                alignment_score=alignment_score,
                created_at=now,
            ))
            s.commit()
        return {"id": art_id, "domain_id": str(spec_id), "spec_id": str(spec_id), "skill_id": skill_id, "alignment_score": alignment_score, "created_at": now.isoformat()}

    def list_artifacts(self, domain_id: UUID) -> list[dict]:
        with self.session() as s:
            rows = (
                s.query(ArtifactHistoryModel)
                .filter(ArtifactHistoryModel.spec_id == str(domain_id))
                .order_by(ArtifactHistoryModel.created_at.desc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "domain_id": r.spec_id,
                    "spec_id": r.spec_id,
                    "skill_id": r.skill_id,
                    "spec_name": r.spec_name,
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
                    "domain_id": r.spec_id,
                    "spec_id": r.spec_id,
                    "skill_id": r.skill_id,
                    "spec_name": r.spec_name,
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
                "domain_id": row.spec_id,
                "spec_id": row.spec_id,
                "skill_id": row.skill_id,
                "spec_name": row.spec_name,
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
        entries = self.get_assertions(domain_id, include_unapproved=True)
        entry_id_to_entry = {str(e.id): e for e in entries}

        with self.session() as s:
            stats_rows = s.query(ChunkUsageStatModel).all()
            # Get all ratings for artifacts in this domain
            artifact_rows = (
                s.query(ArtifactHistoryModel)
                .filter(ArtifactHistoryModel.spec_id == str(domain_id))
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
                "assertion_type": str(e.assertion_type) if e else "",
                "times_used": stat.times_used,
                "avg_rating": round(stat.avg_rating, 2),
                "boost_factor": round(stat.boost_factor, 2),
                "priority": e.priority if e else 0,
            }

        return {
            "domain_id": str(domain_id),
            "spec_id": str(domain_id),
            "chunks": list(heatmap.values()),
            "total_chunks_used": len(heatmap),
            "avg_boost": round(
                sum(v["boost_factor"] for v in heatmap.values()) / max(len(heatmap), 1), 2
            ),
        }

    def get_spec_coverage(self, domain_id: UUID) -> dict:
        """Which parts of the spec are used most vs ignored."""
        entries = self.get_assertions(domain_id, include_unapproved=True)
        audiences = self.get_audiences(domain_id)

        with self.session() as s:
            stats_rows = s.query(ChunkUsageStatModel).all()

        used_chunk_ids = {s.chunk_id for s in stats_rows}
        used_times = {s.chunk_id: s.times_used for s in stats_rows}

        # Group by section type
        by_section: dict = {}
        for e in entries:
            chunk_id = f"chunk-{e.id}"
            st = str(e.assertion_type)
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
            "spec_id": str(domain_id),
            "by_section": by_section,
            "most_used": [
                {"chunk_id": cid, "times_used": times, "content": entry_map.get(cid, "")}
                for cid, times in chunk_usage[:10]
            ],
            "unused_chunks": [
                {"chunk_id": f"chunk-{e.id}", "content": e.content[:80], "assertion_type": str(e.assertion_type)}
                for e in entries
                if f"chunk-{e.id}" not in used_chunk_ids
            ],
            "audience_coverage": {
                p.name: {
                    "has_messages": any(p.name in (e.audiences or []) for e in entries),
                    "message_count": sum(1 for e in entries if p.name in (e.audiences or [])),
                }
                for p in audiences
            },
        }

    get_spec_coverage = get_spec_coverage  # Deprecated alias

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
        _invalidate_graph()
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

    # --- Departments ---

    def create_department(self, name: str, primary_schema_type: str,
                          description: str = "", workspace_id: str = "default") -> dict:
        with self.session() as s:
            existing = s.get(DepartmentModel, name)
            if existing:
                existing.primary_schema_type = primary_schema_type
                existing.description = description
                existing.workspace_id = workspace_id
            else:
                s.add(DepartmentModel(name=name, primary_schema_type=primary_schema_type,
                                       description=description, workspace_id=workspace_id))
            s.commit()
            row = s.get(DepartmentModel, name)
            return {"name": row.name, "primary_schema_type": row.primary_schema_type,
                    "description": row.description, "workspace_id": row.workspace_id}

    def list_departments(self, workspace_id: str | None = None) -> list[dict]:
        with self.session() as s:
            q = s.query(DepartmentModel)
            if workspace_id and workspace_id != "all":
                q = q.filter(DepartmentModel.workspace_id == workspace_id)
            rows = q.order_by(DepartmentModel.name).all()
            return [{"name": r.name, "primary_schema_type": r.primary_schema_type,
                     "description": r.description, "workspace_id": r.workspace_id} for r in rows]

    def get_department(self, name: str, workspace_id: str | None = None) -> dict | None:
        with self.session() as s:
            row = s.get(DepartmentModel, name)
            if not row:
                return None
            return {"name": row.name, "primary_schema_type": row.primary_schema_type,
                    "description": row.description, "workspace_id": row.workspace_id}

    def delete_department(self, name: str, workspace_id: str | None = None) -> bool:
        if name in ("General", "Product Marketing", "Company Marketing", "Enablement", "Product Management"):
            raise ValueError("Cannot delete built-in departments")
        with self.session() as s:
            dept = s.get(DepartmentModel, name)
            if not dept:
                return False
            s.delete(dept)
            s.commit()
            return True

    def get_channel_message_count(self, channel_id: str) -> int:
        """Count how many key messages are associated with a channel."""
        from sqlalchemy import select, func
        with self.session() as s:
            result = s.execute(
                select(func.count()).select_from(assertion_channel_association).where(
                    assertion_channel_association.c.channel_id == channel_id
                )
            ).scalar()
            return result or 0

    # --- Workspace-scoped domain list ---

    def list_specs(self, workspace_id: str | None = None) -> list[Spec]:
        with self.session() as s:
            q = s.query(SpecModel)
            if workspace_id and workspace_id != "all":
                q = q.filter(SpecModel.workspace_id == workspace_id)
            rows = q.all()
            return [_domain_from_row(r) for r in rows]

    list_specs = list_specs  # Deprecated alias

    def list_specs_with_counts(self, workspace_id: str | None = None) -> list[dict]:
        """Return domains with pre-aggregated entry/audience counts — avoids N+1."""
        from sqlalchemy import func
        with self.session() as s:
            entry_counts = (
                s.query(AssertionModel.spec_id, func.count().label("cnt"))
                .group_by(AssertionModel.spec_id)
                .subquery()
            )
            audience_counts = (
                s.query(AudienceModel.spec_id, func.count().label("cnt"))
                .group_by(AudienceModel.spec_id)
                .subquery()
            )
            q = (
                s.query(
                    SpecModel,
                    func.coalesce(entry_counts.c.cnt, 0).label("entry_count"),
                    func.coalesce(audience_counts.c.cnt, 0).label("audience_count"),
                )
                .outerjoin(entry_counts, SpecModel.id == entry_counts.c.spec_id)
                .outerjoin(audience_counts, SpecModel.id == audience_counts.c.spec_id)
            )
            if workspace_id and workspace_id != "all":
                q = q.filter(SpecModel.workspace_id == workspace_id)
            return [
                {
                    "domain": _domain_from_row(row),
                    "entry_count": int(ec),
                    "audience_count": int(pc),
                    # Backward-compat keys
                    "spec": _domain_from_row(row),
                    "message_count": int(ec),
                }
                for row, ec, pc in q.all()
            ]

    list_specs_with_counts = list_specs_with_counts  # Deprecated alias

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
        _invalidate_graph()
        return True

    # --- Source Files ---

    def upsert_source_file(
        self,
        connection_id: str,
        drive_file_id: str,
        file_name: str,
        mime_type: str = "",
        drive_modified_at: str = "",
        spec_id: str | None = None,
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
                if spec_id is not None:
                    row.spec_id = spec_id
            else:
                s.add(SourceFileModel(
                    id=str(uuid4()),
                    connection_id=connection_id,
                    drive_file_id=drive_file_id,
                    file_name=file_name,
                    mime_type=mime_type,
                    spec_id=spec_id,
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
        """Update assertion status and log the action to review_logs."""
        valid = {"draft", "in_review", "approved", "outdated", "locked"}
        if status not in valid:
            raise ValueError(f"Invalid status. Must be one of: {valid}")
        with self.session() as s:
            entry = s.get(AssertionModel, entry_id)
            if not entry:
                return None
            # Promotion gate: content_tier must be set before approving or locking
            if status in ("approved", "locked") and not entry.content_tier:
                raise ValueError("Content tier must be assigned before entry can be approved or locked.")
            entry.status = status
            if status == "approved":
                entry.approved_by = approved_by or "admin"
                entry.approved_at = _now()
            log = ReviewLogModel(
                id=str(uuid4()),
                spec_id=entry.spec_id,
                assertion_id=entry_id,
                action=status,
                performed_by=approved_by or "admin",
                timestamp=_now(),
                notes=notes,
            )
            s.add(log)
            s.commit()
            return {"id": entry_id, "status": entry.status, "approved_by": entry.approved_by}

    update_message_status = update_entry_status  # Deprecated alias

    def update_entry_tier(self, entry_id: str, tier: str | None) -> dict | None:
        """Set or clear the content tier on a assertion."""
        valid_tiers = {"tier_1_locked", "tier_2_structured", "tier_3_grounded", None}
        if tier is not None and tier not in valid_tiers:
            raise ValueError(f"Invalid tier. Must be one of: tier_1_locked, tier_2_structured, tier_3_grounded")
        with self.session() as s:
            entry = s.get(AssertionModel, entry_id)
            if not entry:
                return None
            entry.content_tier = tier
            log = ReviewLogModel(
                id=str(uuid4()),
                spec_id=entry.spec_id,
                assertion_id=entry_id,
                action="tier_update",
                performed_by="admin",
                timestamp=_now(),
                notes=f"Content tier set to {tier}" if tier else "Content tier cleared",
            )
            s.add(log)
            s.commit()
            return {"id": entry_id, "content_tier": entry.content_tier}

    def set_domain_dri(self, domain_id: str, dri: str, performed_by: str = "admin") -> dict | None:
        with self.session() as s:
            dom = s.get(SpecModel, domain_id)
            if not dom:
                return None
            old_dri = dom.dri or "(unassigned)"
            dom.dri = dri
            s.add(ReviewLogModel(
                id=str(uuid4()),
                spec_id=domain_id,
                assertion_id=None,
                action="dri_transfer",
                performed_by=performed_by,
                timestamp=_now(),
                notes=f"Domain DRI changed from {old_dri} to {dri or '(unassigned)'}",
            ))
            s.commit()
            return {"id": domain_id, "dri": dom.dri}

    def set_entry_dri(self, entry_id: str, dri: str, performed_by: str = "admin") -> dict | None:
        with self.session() as s:
            entry = s.get(AssertionModel, entry_id)
            if not entry:
                return None
            old_dri = entry.dri or "(unassigned)"
            entry.dri = dri
            s.add(ReviewLogModel(
                id=str(uuid4()),
                spec_id=entry.spec_id,
                assertion_id=entry_id,
                action="dri_transfer",
                performed_by=performed_by,
                timestamp=_now(),
                notes=f"Entry DRI changed from {old_dri} to {dri or '(unassigned)'}",
            ))
            s.commit()
            return {"id": entry_id, "dri": entry.dri}

    def get_effective_dri(self, entry_id: str) -> str:
        with self.session() as s:
            entry = s.get(AssertionModel, entry_id)
            if not entry:
                return ""
            if entry.dri:
                return entry.dri
            dom = s.get(SpecModel, entry.spec_id)
            return dom.dri if dom else ""

    def get_dri_summary(self) -> dict:
        """Accountability view: domains grouped by DRI, unowned items first.

        A domain is unowned when it has no DRI; an entry is unowned when
        neither it nor its domain has a DRI.
        """
        with self.session() as s:
            domains = s.query(SpecModel).all()
            by_dri: dict[str, list[dict]] = {}
            unowned: list[dict] = []
            for dom in domains:
                entry_rows = s.query(AssertionModel).filter(
                    AssertionModel.spec_id == dom.id
                ).all()
                unowned_entries = (
                    [str(e.id) for e in entry_rows if not e.dri] if not dom.dri else []
                )
                last_reviewed = dom.last_reviewed
                is_stale = (
                    (datetime.now() - last_reviewed).days > 90 if last_reviewed else True
                )
                info = {
                    "domain_id": str(dom.id),
                    "name": dom.name,
                    "dri": dom.dri or "",
                    "department": dom.department,
                    "entry_count": len(entry_rows),
                    "unowned_entry_count": len(unowned_entries),
                    "is_stale": is_stale,
                    "last_reviewed": last_reviewed.isoformat() if last_reviewed else None,
                }
                if dom.dri:
                    by_dri.setdefault(dom.dri, []).append(info)
                else:
                    unowned.append(info)
            return {
                "unowned": unowned,
                "by_dri": by_dri,
                "dri_count": len(by_dri),
                "unowned_count": len(unowned),
            }

    def bulk_update_entry_status(self, entry_ids: list[str], status: str, approved_by: str = "") -> int:
        """Bulk update status for multiple entries. Returns count updated."""
        updated = 0
        for eid in entry_ids:
            result = self.update_entry_status(eid, status, approved_by)
            if result:
                updated += 1
        return updated

    bulk_update_message_status = bulk_update_entry_status  # Deprecated alias

    def get_review_log(self, spec_id: str, limit: int = 50) -> list[dict]:
        with self.session() as s:
            rows = (
                s.query(ReviewLogModel)
                .filter(ReviewLogModel.spec_id == str(spec_id))
                .order_by(ReviewLogModel.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "message_id": r.assertion_id,
                    "entry_id": r.assertion_id,
                    "action": r.action,
                    "performed_by": r.performed_by,
                    "timestamp": r.timestamp.isoformat(),
                    "notes": r.notes,
                }
                for r in rows
            ]

    # ── Query Audit Log ──────────────────────────────────────────────────────

    # ── Phase 4: Staleness / Last Reviewed ───────────────────────────────────

    def mark_domain_reviewed(self, domain_id: str, reviewed_by: str = "admin") -> dict | None:
        """Set last_reviewed = now() and append a review log entry."""
        with self.session() as s:
            domain = s.get(SpecModel, str(domain_id))
            if not domain:
                return None
            domain.last_reviewed = _now()
            log = ReviewLogModel(
                id=str(uuid4()),
                spec_id=str(domain_id),
                assertion_id=None,
                action="reviewed",
                performed_by=reviewed_by,
                timestamp=_now(),
                notes="Spec domain marked as reviewed",
            )
            s.add(log)
            s.commit()
            return {"domain_id": str(domain_id), "spec_id": str(domain_id), "last_reviewed": domain.last_reviewed.isoformat()}

    mark_spec_reviewed = mark_domain_reviewed  # Deprecated alias

    def get_stale_domains(self, days: int = 90) -> list[dict]:
        """Return domains not reviewed in the last `days` days."""
        from datetime import timedelta
        cutoff = _now() - timedelta(days=days)
        with self.session() as s:
            rows = s.query(SpecModel).filter(
                (SpecModel.last_reviewed == None) | (SpecModel.last_reviewed < cutoff)  # noqa: E711
            ).all()
            return [
                {
                    "id": r.id,
                    "domain_id": r.id,
                    "spec_id": r.id,
                    "name": r.name,
                    "last_reviewed": r.last_reviewed.isoformat() if r.last_reviewed else None,
                }
                for r in rows
            ]

    get_stale_specs = get_stale_domains  # Deprecated alias

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
        """Return assertions with usage stats for the heatmap, sorted by times_used desc."""
        with self.session() as s:
            entries = s.query(AssertionModel).filter(
                AssertionModel.spec_id == str(domain_id)
            ).all()
            result = []
            for e in entries:
                stat = s.get(ChunkUsageStatModel, e.source_chunk_id) if e.source_chunk_id else None
                result.append({
                    "id": e.id,
                    "content": e.content,
                    "assertion_type": e.assertion_type,
                    "status": e.status,
                    "times_used": stat.times_used if stat else 0,
                    "avg_rating": round(stat.avg_rating, 1) if stat else 0.0,
                    "boost_factor": round(stat.boost_factor, 2) if stat else 1.0,
                })
            result.sort(key=lambda x: x["times_used"], reverse=True)
            return result

    get_message_usage_stats = get_entry_usage_stats  # Deprecated alias

    # ==========================================
    # Artifact Entry Bindings Helpers
    # ==========================================
    def bind_artifact_entry(self, artifact_id: str | UUID, entry_id: str | UUID, element_type: str, text: str) -> str:
        binding_id = str(uuid4())
        model = ArtifactEntryBindingModel(
            id=binding_id,
            artifact_id=str(artifact_id),
            assertion_id=str(entry_id),
            element_type=element_type,
            bound_text=text,
            created_at=_now()
        )
        with self.session_factory() as session:
            session.add(model)
            session.commit()
        return binding_id

    def get_bindings_for_artifact(self, artifact_id: str | UUID) -> list[dict]:
        with self.session_factory() as session:
            models = session.query(ArtifactEntryBindingModel).filter(
                ArtifactEntryBindingModel.artifact_id == str(artifact_id)
            ).all()
            return [
                {
                    "id": UUID(m.id),
                    "artifact_id": UUID(m.artifact_id),
                    "assertion_id": UUID(m.assertion_id),
                    "element_type": m.element_type,
                    "bound_text": m.bound_text
                }
                for m in models
            ]

    # ==========================================
    # Graph: entities, mentions, typed edges
    # ==========================================

    @staticmethod
    def normalize_entity_name(name: str) -> str:
        """Fold a surface form to its match key. Deliberately aggressive —
        'Payments API', 'payments-api' and 'payments_api' are one entity."""
        return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()

    def resolve_entity(
        self,
        name: str,
        entity_type: str = "concept",
        workspace_id: str = "default",
        description: str = "",
        create: bool = True,
    ) -> Optional[str]:
        """Find or create the entity for a surface form. Returns its id.

        Resolution is exact-match on the normalized name or on a registered
        alias. Embedding-similarity merging is deliberately not done here —
        a false merge silently fuses two unrelated services and is much harder
        to notice than a duplicate. Ambiguous cases become separate entities
        and can be merged explicitly with merge_entities().
        """
        norm = self.normalize_entity_name(name)
        if not norm:
            return None
        with self.session() as s:
            row = s.query(EntityModel).filter(
                EntityModel.workspace_id == workspace_id,
                EntityModel.normalized_name == norm,
            ).first()
            if row:
                return row.id
            # alias match
            for cand in s.query(EntityModel).filter(EntityModel.workspace_id == workspace_id).all():
                if norm in {self.normalize_entity_name(a) for a in json.loads(cand.aliases or "[]")}:
                    return cand.id
            if not create:
                return None
            eid = str(uuid4())
            s.add(EntityModel(
                id=eid, workspace_id=workspace_id, name=name, normalized_name=norm,
                entity_type=entity_type, description=description, aliases="[]",
                created_at=_now(),
            ))
            s.commit()
        _invalidate_graph()
        return eid

    def merge_entities(self, keep_id: str, merge_id: str) -> int:
        """Fold merge_id into keep_id: repoint mentions and edges, absorb the
        alias, delete the loser. Returns rows repointed."""
        if keep_id == merge_id:
            return 0
        moved = 0
        with self.session() as s:
            keep = s.get(EntityModel, keep_id)
            loser = s.get(EntityModel, merge_id)
            if not keep or not loser:
                return 0
            aliases = set(json.loads(keep.aliases or "[]"))
            aliases.add(loser.name)
            aliases.update(json.loads(loser.aliases or "[]"))
            keep.aliases = json.dumps(sorted(aliases))
            moved += s.query(EntityMentionModel).filter(
                EntityMentionModel.entity_id == merge_id
            ).update({"entity_id": keep_id})
            moved += s.query(EdgeModel).filter(
                EdgeModel.src_type == "entity", EdgeModel.src_id == merge_id
            ).update({"src_id": keep_id})
            moved += s.query(EdgeModel).filter(
                EdgeModel.dst_type == "entity", EdgeModel.dst_id == merge_id
            ).update({"dst_id": keep_id})
            s.delete(loser)
            s.commit()
        _invalidate_graph()
        return moved

    def add_entity_mention(
        self, entity_id: str, assertion_id: str, spec_id: str, confidence: float = 1.0
    ) -> Optional[str]:
        with self.session() as s:
            existing = s.query(EntityMentionModel).filter(
                EntityMentionModel.entity_id == entity_id,
                EntityMentionModel.assertion_id == assertion_id,
            ).first()
            if existing:
                return existing.id
            mid = str(uuid4())
            s.add(EntityMentionModel(
                id=mid, entity_id=entity_id, assertion_id=str(assertion_id),
                spec_id=str(spec_id), confidence=confidence, created_at=_now(),
            ))
            s.commit()
        _invalidate_graph()
        return mid

    def list_entities(self, workspace_id: str = "default") -> list[dict]:
        with self.session() as s:
            rows = s.query(EntityModel).filter(EntityModel.workspace_id == workspace_id).all()
            return [{
                "id": r.id, "name": r.name, "normalized_name": r.normalized_name,
                "entity_type": r.entity_type, "description": r.description,
                "aliases": json.loads(r.aliases or "[]"),
            } for r in rows]

    def list_entity_mentions(self, workspace_id: str = "default") -> list[dict]:
        with self.session() as s:
            rows = (
                s.query(EntityMentionModel)
                .join(EntityModel, EntityModel.id == EntityMentionModel.entity_id)
                .filter(EntityModel.workspace_id == workspace_id)
                .all()
            )
            return [{
                "entity_id": r.entity_id, "assertion_id": r.assertion_id,
                "spec_id": r.spec_id, "confidence": r.confidence,
            } for r in rows]

    def _node_exists(self, node_type: str, node_id: str) -> bool:
        table = {"assertion": AssertionModel, "spec": SpecModel, "entity": EntityModel}.get(node_type)
        if table is None:
            return False
        with self.session() as s:
            return s.get(table, str(node_id)) is not None

    def add_edge(
        self,
        src_type: str, src_id: str,
        dst_type: str, dst_id: str,
        rel_type: str,
        confidence: float = 1.0,
        provenance: str = "",
        created_by: str = "",
        workspace_id: str = "default",
    ) -> str:
        """Create a typed edge. Raises ValueError if either endpoint is missing —
        SQLite cannot express a polymorphic FK, so integrity is checked here."""
        for t, i, lbl in ((src_type, src_id, "src"), (dst_type, dst_id, "dst")):
            if not self._node_exists(t, i):
                raise ValueError(f"{lbl} node not found: {t}:{i}")
        with self.session() as s:
            existing = s.query(EdgeModel).filter(
                EdgeModel.src_type == src_type, EdgeModel.src_id == str(src_id),
                EdgeModel.dst_type == dst_type, EdgeModel.dst_id == str(dst_id),
                EdgeModel.rel_type == rel_type,
            ).first()
            if existing:
                return existing.id
            eid = str(uuid4())
            s.add(EdgeModel(
                id=eid, workspace_id=workspace_id,
                src_type=src_type, src_id=str(src_id),
                dst_type=dst_type, dst_id=str(dst_id),
                rel_type=rel_type, confidence=confidence,
                provenance=provenance, created_by=created_by, created_at=_now(),
            ))
            s.commit()
        _invalidate_graph()
        return eid

    def delete_edge(self, edge_id: str) -> bool:
        with self.session() as s:
            row = s.get(EdgeModel, edge_id)
            if not row:
                return False
            s.delete(row)
            s.commit()
        _invalidate_graph()
        return True

    def list_edges(
        self,
        workspace_id: str = "default",
        rel_type: Optional[str] = None,
        src_id: Optional[str] = None,
        dst_id: Optional[str] = None,
    ) -> list[dict]:
        with self.session() as s:
            q = s.query(EdgeModel).filter(EdgeModel.workspace_id == workspace_id)
            if rel_type:
                q = q.filter(EdgeModel.rel_type == rel_type)
            if src_id:
                q = q.filter(EdgeModel.src_id == str(src_id))
            if dst_id:
                q = q.filter(EdgeModel.dst_id == str(dst_id))
            return [{
                "id": r.id, "src_type": r.src_type, "src_id": r.src_id,
                "dst_type": r.dst_type, "dst_id": r.dst_id, "rel_type": r.rel_type,
                "confidence": r.confidence, "provenance": r.provenance,
                "created_by": r.created_by,
            } for r in q.all()]

    def get_dependents(self, node_type: str, node_id: str) -> list[dict]:
        """Edges whose destination is this node via a propagating relationship —
        i.e. everything that goes stale when this node changes."""
        with self.session() as s:
            rows = s.query(EdgeModel).filter(
                EdgeModel.dst_type == node_type,
                EdgeModel.dst_id == str(node_id),
                EdgeModel.rel_type.in_(sorted(PROPAGATING_RELS)),
            ).all()
            return [{
                "id": r.id, "src_type": r.src_type, "src_id": r.src_id,
                "rel_type": r.rel_type, "confidence": r.confidence,
            } for r in rows]

    def propagate_change(
        self, node_type: str, node_id: str, max_depth: int = 5, _seen: set | None = None
    ) -> list[dict]:
        """Cascade staleness along inbound DEPENDS_ON / INFORMS edges.

        When a node changes, everything that declared a dependency on it is
        marked outdated and the transition is written to the review trail.
        Recurses so a chain A -> B -> C fully invalidates, with a visited set
        guarding against cycles (nothing prevents an author creating one).

        Returns the list of nodes marked stale.
        """
        seen = _seen if _seen is not None else set()
        key = (node_type, str(node_id))
        if key in seen or max_depth <= 0:
            return []
        seen.add(key)

        affected: list[dict] = []
        for dep in self.get_dependents(node_type, node_id):
            src_type, src_id = dep["src_type"], dep["src_id"]
            if (src_type, src_id) in seen:
                continue
            with self.session() as s:
                if src_type == "assertion":
                    row = s.get(AssertionModel, src_id)
                    if row and row.status != "outdated":
                        row.status = "outdated"
                        s.add(ReviewLogModel(
                            id=str(uuid4()),
                            spec_id=str(row.spec_id),
                            assertion_id=src_id,
                            action="propagation_drift",
                            performed_by="system_graph",
                            timestamp=datetime.now(),
                            notes=(
                                f"Marked outdated: {dep['rel_type']} edge to "
                                f"{node_type}:{node_id}, which changed."
                            ),
                        ))
                        s.commit()
                        affected.append({
                            "node_type": src_type, "node_id": src_id,
                            "rel_type": dep["rel_type"], "spec_id": str(row.spec_id),
                        })
                elif src_type == "spec":
                    row = s.get(SpecModel, src_id)
                    if row and row.status != "needs_review":
                        row.status = "needs_review"
                        s.commit()
                        affected.append({
                            "node_type": src_type, "node_id": src_id,
                            "rel_type": dep["rel_type"],
                        })
            affected.extend(
                self.propagate_change(src_type, src_id, max_depth - 1, seen)
            )
        return affected

    def check_spec_completeness(self, domain_id: UUID) -> dict:
        domain = self.get_spec(domain_id)
        if not domain:
            return {"score": 0, "missing_sections": [], "error": "Domain not found"}

        entries = self.get_assertions(domain_id, include_unapproved=True)
        present_sections = {str(e.assertion_type) for e in entries if e.assertion_type}
        from src.models import AssertionType
        all_assertion_types = [st.value for st in AssertionType
                             if st not in (AssertionType.SOURCE_MARKDOWN,)]

        # Core fields that contribute to the score
        core_fields = {
            "name": bool(domain.name),
            "summary": bool(domain.summary),
            "audience": bool(domain.audience),
            "brand_personality": bool(domain.brand_personality),
            "positioning": bool(domain.positioning),
            "tagline": bool(domain.tagline),
            "differentiation": bool(domain.differentiation),
        }
        field_score = sum(10 for v in core_fields.values() if v)

        entry_count = len(entries)
        if entry_count >= 3:
            field_score += 10
        if entry_count >= 6:
            field_score += 10

        audiences = self.get_audiences(domain_id)
        if len(audiences) >= 1:
            field_score += 5

        missing_sections = [st for st in all_assertion_types if st not in present_sections]

        return {
            "score": min(field_score, 100),
            "missing_sections": missing_sections,
            "present_sections": sorted(present_sections),
            "total_entries": entry_count,
            "total_audiences": len(audiences),
            "core_fields": core_fields,
        }


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
        "domain_id": row.spec_id,
        "spec_id": row.spec_id,
        "drive_modified_at": row.drive_modified_at,
        "sync_status": row.sync_status,
        "error_message": row.error_message,
        "synced_at": row.synced_at.isoformat() if row.synced_at else None,
    }


def _safe_assertion_type(value: str) -> AssertionType:
    try:
        return AssertionType(value)
    except ValueError:
        return AssertionType.POSITIONING


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


def _domain_from_row(row: SpecModel) -> Spec:
    # Text columns are nullable in databases created before these fields had
    # defaults, and the model declares them non-optional. Coerce rather than
    # reject: a legacy row with a NULL summary is still a valid Spec.
    def _s(v: str | None) -> str:
        return v or ""

    return Spec(
        id=UUID(row.id),
        name=_s(row.name),
        source=_s(row.source) or "manual",
        source_id=row.source_id,
        schema_type=row.schema_type or "engineering_spec",
        summary=_s(row.summary),
        audience=_s(row.audience),
        brand_personality=_s(row.brand_personality),
        positioning=_s(row.positioning),
        tagline=_s(row.tagline),
        differentiation=_s(row.differentiation),
        status=SpecStatus(row.status or "active"),
        department=_s(row.department) or "General",
        last_synced=row.last_synced,
        last_reviewed=row.last_reviewed,
        # Phase 2 additions:
        parent_domain_id=UUID(row.parent_domain_id) if row.parent_domain_id else None,
        inheritance_policy=InheritancePolicy(row.inheritance_policy) if row.inheritance_policy else InheritancePolicy.FULL,
        dri=row.dri or "",
    )


_spec_from_row = _domain_from_row  # Deprecated alias


def _entry_from_row(row: AssertionModel) -> Assertion:
    return Assertion(
        id=UUID(row.id),
        spec_id=UUID(row.spec_id),
        pillar_id=row.pillar_id,
        assertion_type=_safe_assertion_type(row.assertion_type),
        priority=row.priority,
        content=row.content,
        status=AssertionStatus(row.status) if row.status else AssertionStatus.DRAFT,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        content_tier=ContentTier(row.content_tier) if row.content_tier else None,
        variants=row.variants or {},
        audiences=row.audiences or [],
        channels=[_safe_channel(c.id if hasattr(c, "id") else str(c)) for c in (row.channels or [])] or ["all"],
        source_chunk_id=row.source_chunk_id,
        dri=row.dri or "",
    )


_msg_from_row = _entry_from_row  # Deprecated alias


def _audience_from_row(row: AudienceModel) -> Audience:
    return Audience(
        id=UUID(row.id),
        spec_id=UUID(row.spec_id),
        name=row.name,
        description=row.description,
        qa_pairs=row.qa_pairs or [],
        status=AssertionStatus(row.status) if row.status else AssertionStatus.DRAFT,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
    )


def _pillar_from_row(row: PillarModel) -> "Pillar":
    from src.models import Pillar
    return Pillar(
        id=row.id,
        spec_id=row.spec_id,
        name=row.name,
        description=row.description,
        display_order=row.display_order,
    )