"""store production target timing snapshots

Revision ID: 0031
Revises: 0030
"""

from alembic import op
import sqlalchemy as sa


revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("production_executions", sa.Column("target_cycle_time_seconds", sa.Numeric(14, 3), nullable=True))
    op.add_column("production_executions", sa.Column("target_finish_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("production_executions", "target_finish_at")
    op.drop_column("production_executions", "target_cycle_time_seconds")
