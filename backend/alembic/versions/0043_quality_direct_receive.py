"""allow quality inspection directly after warehouse receiving

Revision ID: 0043_qc_direct_receive
Revises: 0042_quality_destination
"""

import sqlalchemy as sa

from alembic import op

revision = "0043_qc_direct_receive"
down_revision = "0042_quality_destination"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "wip_lot_jobs",
        "process_code",
        existing_type=sa.String(length=20),
        nullable=True,
    )
    op.alter_column(
        "quality_inspections",
        "before_process_code",
        existing_type=sa.String(length=20),
        nullable=True,
    )


def downgrade() -> None:
    # Keep direct-receiving inspection history valid after this migration.
    pass
