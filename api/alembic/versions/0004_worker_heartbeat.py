"""Worker heartbeat for production health reporting.

A worker upserts its liveness here every poll; the health endpoint reads the
freshest heartbeat to report whether background processing is actually
running — impossible to tell from the job queue alone when it is idle.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeat",
        sa.Column("worker_id", sa.Text, primary_key=True),
        sa.Column("kinds", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "started_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "last_seen", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("worker_heartbeat")
