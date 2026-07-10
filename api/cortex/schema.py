"""Durable data model.

Design positions (from the handbook):
- The unit of knowledge is the *semantic artifact* — a structural unit
  (module/class/function/doc section) with stable identity, relationships,
  and multiple representations — not a fixed-size chunk.
- Fixed-size chunks exist only as the baseline RAG's units, stored
  separately so the benchmark comparison stays honest.
- Source versions are append-only: re-ingestion creates a new version and
  supersedes the old one. Benchmarks cite immutable version ids.
- One PostgreSQL database carries everything: knowledge, embeddings,
  executions, events, and the job queue. No extra services.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    text,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Dimension of the default embedding model (nomic-embed-text).
# Changing the embedding model to a different dimension requires a migration.
EMBED_DIM = 768


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# --------------------------------------------------------------------------
# Sources and versions
# --------------------------------------------------------------------------


class Source(Base):
    """One ingested corpus — a Git repository."""

    __tablename__ = "source"

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[str] = mapped_column(String(32), default="git_repo", nullable=False)
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class SourceVersion(Base):
    """Immutable snapshot of a source at one commit. Append-only."""

    __tablename__ = "source_version"

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source.id"), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ingesting", nullable=False)
    # 'ingesting' | 'ready' | 'failed' | 'superseded'
    stats: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False)
    ingested_at: Mapped[datetime] = _created_at()


class SourceFile(Base):
    __tablename__ = "source_file"
    __table_args__ = (UniqueConstraint("source_version_id", "path"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_version.id"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(32))
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)


# --------------------------------------------------------------------------
# Semantic artifacts, relationships, embeddings
# --------------------------------------------------------------------------


class SemanticArtifact(Base):
    """A structural knowledge unit with stable identity.

    Representation ladder maps to columns, not rows:
      L0 entity reference  -> qualified_name
      L1 atomic facts      -> facts
      L2 relationships     -> artifact_edge rows
      L3 compressed claim  -> summary_text (generated lazily, cached)
      L4/L5 source excerpt/full -> raw_text
    """

    __tablename__ = "semantic_artifact"
    __table_args__ = (UniqueConstraint("source_version_id", "qualified_name"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_version.id"), nullable=False, index=True
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_file.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # 'module' | 'class' | 'function' | 'method' | 'doc_section' | 'config_entry'
    qualified_name: Mapped[str] = mapped_column(Text, nullable=False)
    span_start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    span_end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    summary_text: Mapped[str | None] = mapped_column(Text)
    facts: Mapped[list | None] = mapped_column(JSONB)
    raw_token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_token_count: Mapped[int | None] = mapped_column(Integer)
    reliability_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False)


class ArtifactEdge(Base):
    """Typed relationship between artifacts — the dependency substrate."""

    __tablename__ = "artifact_edge"

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_version.id"), nullable=False, index=True
    )
    from_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("semantic_artifact.id"), nullable=False, index=True
    )
    to_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("semantic_artifact.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # 'imports' | 'calls' | 'inherits' | 'contains' | 'references_doc'
    # | 'documents' | 'supersedes'
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False)


class ArtifactEmbedding(Base):
    __tablename__ = "artifact_embedding"
    __table_args__ = (UniqueConstraint("artifact_id", "representation", "model_name"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("semantic_artifact.id"), nullable=False, index=True
    )
    representation: Mapped[str] = mapped_column(String(16), nullable=False)  # 'raw' | 'summary'
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM), nullable=False)


# --------------------------------------------------------------------------
# Baseline RAG units (kept separate on purpose — benchmark fairness)
# --------------------------------------------------------------------------


class BaselineChunk(Base):
    __tablename__ = "baseline_chunk"
    __table_args__ = (UniqueConstraint("source_file_id", "chunk_index"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_version.id"), nullable=False, index=True
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_file.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))


# --------------------------------------------------------------------------
# Executions and events
# --------------------------------------------------------------------------


class Execution(Base):
    """One query answered by either pipeline (cortex or baseline)."""

    __tablename__ = "execution"

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_version.id"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)  # 'cortex' | 'baseline'
    query: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="running", nullable=False)
    # 'running' | 'succeeded' | 'failed'
    failure_reason: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False)
    model_config_: Mapped[dict] = mapped_column("model_config", JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False)
    started_at: Mapped[datetime] = _created_at()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExecutionEvent(Base):
    """Append-only typed event stream — powers Studio, traces, benchmarks."""

    __tablename__ = "execution_event"
    __table_args__ = (UniqueConstraint("execution_id", "seq"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("execution.id"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False)
    created_at: Mapped[datetime] = _created_at()


# --------------------------------------------------------------------------
# Job queue (the database is the queue)
# --------------------------------------------------------------------------


class Job(Base):
    __tablename__ = "job"

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # 'ingest_source' | 'run_benchmark' | 'reap_orphans'
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    # 'queued' | 'running' | 'waiting_model' | 'cancellation_requested'
    # | 'succeeded' | 'failed' | 'cancelled'
    # Real progress reported by the worker at safe boundaries. `stage` is a
    # short machine name (e.g. 'cloning', 'embedding'); `progress` carries
    # {"done": int, "total": int|null} when a total is honestly known.
    stage: Mapped[str | None] = mapped_column(String(32))
    progress: Mapped[dict | None] = mapped_column(JSONB)
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    locked_by: Mapped[str | None] = mapped_column(String(128))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_seconds: Mapped[int] = mapped_column(
        Integer, default=600, server_default="600", nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
