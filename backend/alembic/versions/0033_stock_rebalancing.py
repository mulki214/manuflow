"""add stock rebalancing audit documents

Revision ID: 0033_stock_rebalancing
Revises: 0032
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa


revision = "0033_stock_rebalancing"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE inventory_movement_type_enum ADD VALUE IF NOT EXISTS 'stock_rebalance_in'")
    op.execute("ALTER TYPE inventory_movement_type_enum ADD VALUE IF NOT EXISTS 'stock_rebalance_out'")
    op.create_table(
        "daily_stock_rebalancing_sequences",
        sa.Column("sequence_date", sa.Date(), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "stock_rebalancings",
        sa.Column("rebalance_number", sa.String(length=20), primary_key=True),
        sa.Column("rebalance_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_stock_rebalancings_rebalance_date", "stock_rebalancings", ["rebalance_date"])
    op.create_index("ix_stock_rebalancings_created_by", "stock_rebalancings", ["created_by"])
    op.create_table(
        "stock_rebalancing_lines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("rebalance_number", sa.String(length=20), sa.ForeignKey("stock_rebalancings.rebalance_number", ondelete="RESTRICT"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("lot_id", sa.Integer(), sa.ForeignKey("product_lots.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_code", sa.String(length=30), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("lot_number", sa.String(length=100), nullable=False),
        sa.Column("plant_code", sa.String(length=10), nullable=False),
        sa.Column("storage_location_code", sa.String(length=20), nullable=False),
        sa.Column("unit", sa.String(length=10), nullable=False),
        sa.Column("system_quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("physical_quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("difference_quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("lot_quantity_after", sa.Numeric(20, 3), nullable=False),
        sa.Column("product_stock_after", sa.Numeric(20, 3), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint("rebalance_number", "line_number", name="uq_stock_rebalance_line"),
    )
    op.create_index("ix_stock_rebalancing_lines_rebalance_number", "stock_rebalancing_lines", ["rebalance_number"])
    op.create_index("ix_stock_rebalancing_lines_lot_id", "stock_rebalancing_lines", ["lot_id"])


def downgrade() -> None:
    op.drop_index("ix_stock_rebalancing_lines_lot_id", table_name="stock_rebalancing_lines")
    op.drop_index("ix_stock_rebalancing_lines_rebalance_number", table_name="stock_rebalancing_lines")
    op.drop_table("stock_rebalancing_lines")
    op.drop_index("ix_stock_rebalancings_created_by", table_name="stock_rebalancings")
    op.drop_index("ix_stock_rebalancings_rebalance_date", table_name="stock_rebalancings")
    op.drop_table("stock_rebalancings")
    op.drop_table("daily_stock_rebalancing_sequences")
    # PostgreSQL enum labels are intentionally retained: existing movement data may use them.
