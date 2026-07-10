"""Job cancellation states and real progress reporting.

- widen job.status so 'cancellation_requested' fits
- add job.stage / job.progress for worker-reported progress

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "job",
        "status",
        existing_type=sa.String(16),
        type_=sa.String(32),
        existing_nullable=False,
    )
    op.add_column("job", sa.Column("stage", sa.String(32), nullable=True))
    op.add_column("job", sa.Column("progress", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("job", "progress")
    op.drop_column("job", "stage")
    op.alter_column(
        "job",
        "status",
        existing_type=sa.String(32),
        type_=sa.String(16),
        existing_nullable=False,
    )
