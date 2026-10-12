"""Per-user repository ownership.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing repositories belong to the open-mode "local" user, so a
    # deployment that turns on per-user tokens keeps them under that name.
    op.add_column(
        "source",
        sa.Column("owner_id", sa.String(64), nullable=False, server_default="local"),
    )
    op.create_index("ix_source_owner_id", "source", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_source_owner_id", table_name="source")
    op.drop_column("source", "owner_id")
