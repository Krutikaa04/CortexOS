"""Initial schema: sources, artifacts, edges, embeddings, baseline chunks,
executions, events, jobs — plus pgvector extension and search indexes.

Revision ID: 0001
Revises:
"""

from alembic import op

from cortex.schema import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # schema.py is the single source of truth for tables in this first migration;
    # subsequent migrations use explicit alembic operations.
    Base.metadata.create_all(bind=bind)

    # Vector similarity (cosine) over artifact and baseline-chunk embeddings.
    op.execute(
        "CREATE INDEX ix_artifact_embedding_hnsw ON artifact_embedding "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_baseline_chunk_hnsw ON baseline_chunk "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    # Lexical full-text search over artifact raw text.
    op.execute(
        "CREATE INDEX ix_semantic_artifact_fts ON semantic_artifact "
        "USING gin (to_tsvector('english', raw_text))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_semantic_artifact_fts")
    op.execute("DROP INDEX IF EXISTS ix_baseline_chunk_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_artifact_embedding_hnsw")
    Base.metadata.drop_all(bind=op.get_bind())
