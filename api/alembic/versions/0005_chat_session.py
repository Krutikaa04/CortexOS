"""Repository-scoped chat sessions (conversation metadata).

Messages remain `execution` rows keyed by session_id; this table only names
and scopes a conversation so Studio can list, rename, switch and delete them.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_session",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_version_id", UUID(as_uuid=True),
            sa.ForeignKey("source_version.id"), nullable=False, index=True,
        ),
        sa.Column("title", sa.String(200), nullable=False, server_default="New chat"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("chat_session")
