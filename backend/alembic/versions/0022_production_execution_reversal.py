"""add production execution reversal audit fields

Revision ID: 0022
Revises: 0021
"""

import sqlalchemy as sa

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("production_executions", sa.Column("reversed_by", sa.String(9), nullable=True))
    op.add_column("production_executions", sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("production_executions", sa.Column("reversal_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_production_executions_reversed_by_users",
        "production_executions",
        "users",
        ["reversed_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_production_executions_reversed_by_users", "production_executions", type_="foreignkey")
    op.drop_column("production_executions", "reversal_reason")
    op.drop_column("production_executions", "reversed_at")
    op.drop_column("production_executions", "reversed_by")
