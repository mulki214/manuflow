"""record BOM yield variance as source-equivalent consumable

Revision ID: 0039_bom_consumable_variance
Revises: 0038_pr_so_link
"""

import sqlalchemy as sa

from alembic import op

revision = "0039_bom_consumable_variance"
down_revision = "0038_pr_so_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "production_executions",
        sa.Column(
            "bom_consumable_quantity",
            sa.Numeric(20, 3),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("production_executions", "bom_consumable_quantity")
