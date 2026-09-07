"""add delivery confirmation and sales order traceability

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE delivery_status_enum ADD VALUE IF NOT EXISTS 'dispatched'")
    op.execute("ALTER TYPE delivery_status_enum ADD VALUE IF NOT EXISTS 'delivered'")
    op.add_column("deliveries", sa.Column("delivered_by", sa.String(9), nullable=True))
    op.add_column("deliveries", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_deliveries_delivered_by_users", "deliveries", "users", ["delivered_by"], ["id"], ondelete="SET NULL"
    )
    op.add_column("warehouse_material_transfers", sa.Column("sales_order_item_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_warehouse_transfers_so_item",
        "warehouse_material_transfers",
        "sales_order_items",
        ["sales_order_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_warehouse_material_transfers_sales_order_item_id", "warehouse_material_transfers", ["sales_order_item_id"]
    )
    op.add_column("wip_lot_jobs", sa.Column("sales_order_item_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_wip_lot_jobs_so_item",
        "wip_lot_jobs",
        "sales_order_items",
        ["sales_order_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_wip_lot_jobs_sales_order_item_id", "wip_lot_jobs", ["sales_order_item_id"])


def downgrade() -> None:
    op.drop_index("ix_wip_lot_jobs_sales_order_item_id", table_name="wip_lot_jobs")
    op.drop_constraint("fk_wip_lot_jobs_so_item", "wip_lot_jobs", type_="foreignkey")
    op.drop_column("wip_lot_jobs", "sales_order_item_id")
    op.drop_index("ix_warehouse_material_transfers_sales_order_item_id", table_name="warehouse_material_transfers")
    op.drop_constraint("fk_warehouse_transfers_so_item", "warehouse_material_transfers", type_="foreignkey")
    op.drop_column("warehouse_material_transfers", "sales_order_item_id")
    op.drop_constraint("fk_deliveries_delivered_by_users", "deliveries", type_="foreignkey")
    op.drop_column("deliveries", "delivered_at")
    op.drop_column("deliveries", "delivered_by")
