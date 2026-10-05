"""store product productivity and production target outcome snapshots

Revision ID: 0035_productivity_target_outcome
Revises: 0034_partial_pr_approval
"""

from alembic import op
import sqlalchemy as sa


revision = "0035_productivity_target_outcome"
down_revision = "0034_partial_pr_approval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("productivity_percentage", sa.Numeric(5, 2), nullable=False, server_default="95"),
    )
    op.add_column(
        "production_executions",
        sa.Column("target_productivity_percentage", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "production_executions",
        sa.Column("target_outcome_quantity", sa.Numeric(20, 3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("production_executions", "target_outcome_quantity")
    op.drop_column("production_executions", "target_productivity_percentage")
    op.drop_column("products", "productivity_percentage")
