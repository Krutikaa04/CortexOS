"""Benchmark runs and Semantic Virtual Memory page residency.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benchmark_run",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_version_id", UUID(as_uuid=True),
                  sa.ForeignKey("source_version.id"), nullable=False),
        sa.Column("config", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(16), server_default="running", nullable=False),
        # 'running' | 'succeeded' | 'failed'
        sa.Column("report", JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "execution",
        sa.Column("benchmark_run_id", UUID(as_uuid=True),
                  sa.ForeignKey("benchmark_run.id"), nullable=True),
    )
    op.create_index("ix_execution_benchmark_run_id", "execution", ["benchmark_run_id"])

    # SVM page residency: one row per (session, artifact). The page's prompt
    # position (seq) must be stable so the model runtime's prefix cache hits.
    op.create_table(
        "svm_page",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", UUID(as_uuid=True),
                  sa.ForeignKey("semantic_artifact.id"), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        # 'active' | 'evicted' | 'invalid'
        sa.Column("seq", sa.Integer, nullable=False),  # position in the stable prompt prefix
        sa.Column("tokens", sa.Integer, nullable=False),
        sa.Column("representation", sa.String(16), nullable=False),
        sa.Column("pinned", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("use_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("session_id", "artifact_id"),
    )
    op.create_index("ix_svm_page_session", "svm_page", ["session_id", "state"])


def downgrade() -> None:
    op.drop_table("svm_page")
    op.drop_index("ix_execution_benchmark_run_id", table_name="execution")
    op.drop_column("execution", "benchmark_run_id")
    op.drop_table("benchmark_run")
