"""Answer cache.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "answer_cache",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("source_version_id", UUID(as_uuid=True),
                  sa.ForeignKey("source_version.id"), nullable=False),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("execution_id", UUID(as_uuid=True), nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("metrics", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("hits", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_answer_cache_version", "answer_cache", ["source_version_id"])


def downgrade() -> None:
    op.drop_index("ix_answer_cache_version", table_name="answer_cache")
    op.drop_table("answer_cache")
