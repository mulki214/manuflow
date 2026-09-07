"""add delivery line items

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_lines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("delivery_number", sa.String(22), sa.ForeignKey("deliveries.delivery_number", ondelete="CASCADE"), nullable=False),
        sa.Column("sales_order_item_id", sa.Integer(), sa.ForeignKey("sales_order_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lot_id", sa.Integer(), sa.ForeignKey("product_lots.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_code", sa.String(30), sa.ForeignKey("products.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("lot_number", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
    )
    op.create_index("ix_delivery_lines_delivery_number", "delivery_lines", ["delivery_number"])


def downgrade() -> None:
    op.drop_index("ix_delivery_lines_delivery_number", table_name="delivery_lines")
    op.drop_table("delivery_lines")
