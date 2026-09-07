"""add quality inspection reversal audit fields

Revision ID: 0021
Revises: 0020
"""

import sqlalchemy as sa

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quality_inspections", sa.Column("reversed_by", sa.String(9), nullable=True))
    op.add_column("quality_inspections", sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("quality_inspections", sa.Column("reversal_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_quality_inspections_reversed_by_users",
        "quality_inspections",
        "users",
        ["reversed_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_quality_inspections_reversed_by_users", "quality_inspections", type_="foreignkey")
    op.drop_column("quality_inspections", "reversal_reason")
    op.drop_column("quality_inspections", "reversed_at")
    op.drop_column("quality_inspections", "reversed_by")
