"""remove driver assignment from transportation master

Revision ID: 0016
Revises: 0015
"""

import sqlalchemy as sa

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("transportations", "driver_name")


def downgrade() -> None:
    op.add_column("transportations", sa.Column("driver_name", sa.String(150), nullable=True))
