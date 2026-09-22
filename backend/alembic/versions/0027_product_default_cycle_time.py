"""add default cycle time to products

Revision ID: 0027
Revises: 0026
"""

import sqlalchemy as sa

from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("default_cycle_time_seconds", sa.Numeric(14, 3), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "default_cycle_time_seconds")
