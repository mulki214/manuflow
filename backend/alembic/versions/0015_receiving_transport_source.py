"""add receiving transport source snapshot

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "receivings",
        sa.Column("transport_source", sa.String(20), server_default="external", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("receivings", "transport_source")
