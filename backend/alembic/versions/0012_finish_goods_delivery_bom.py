"""add finish goods delivery and bom

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE TYPE product_category_enum AS ENUM ('raw_material', 'work_in_progress', 'finished_good')")
    op.add_column(
        "products",
        sa.Column(
            "category",
            sa.Enum("raw_material", "work_in_progress", "finished_good", name="product_category_enum"),
            server_default="finished_good",
            nullable=False,
        ),
    )
    op.create_index("ix_products_category", "products", ["category"])
    op.execute("CREATE TYPE finish_good_status_enum AS ENUM ('posted', 'reversed')")
    op.execute("CREATE TYPE delivery_status_enum AS ENUM ('posted', 'reversed')")
    op.create_table(
        "daily_finish_good_sequences",
        sa.Column("sequence_date", sa.Date(), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False),
    )
    op.create_table(
        "daily_delivery_sequences",
        sa.Column("sequence_date", sa.Date(), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False),
    )
    op.create_table(
        "bill_of_material_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("finished_product_code", sa.String(15), nullable=False),
        sa.Column("material_product_code", sa.String(15), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["finished_product_code"], ["products.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_product_code"], ["products.code"], ondelete="RESTRICT"),
        sa.UniqueConstraint("finished_product_code", "material_product_code", name="uq_bom_finished_material"),
    )
    op.create_table(
        "finish_good_receipts",
        sa.Column("receipt_number", sa.String(22), primary_key=True),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("source_wip_job_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("product_code", sa.String(15), nullable=False),
        sa.Column("lot_number", sa.String(100), nullable=False),
        sa.Column("lot_segment_code", sa.String(40), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("plant_code", sa.String(5), nullable=False),
        sa.Column("storage_location_code", sa.String(15), nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("posted", "reversed", name="finish_good_status_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("performed_by", sa.String(9), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_wip_job_id"], ["wip_lot_jobs.id"]),
        sa.ForeignKeyConstraint(["product_code"], ["products.code"]),
        sa.ForeignKeyConstraint(["plant_code"], ["plants.code"]),
        sa.ForeignKeyConstraint(["storage_location_code"], ["storage_locations.code"]),
        sa.ForeignKeyConstraint(["lot_id"], ["product_lots.id"]),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"]),
    )
    op.create_table(
        "deliveries",
        sa.Column("delivery_number", sa.String(22), primary_key=True),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("sales_order_item_id", sa.Integer(), nullable=False),
        sa.Column("sales_order_number", sa.String(20), nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("product_code", sa.String(15), nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("lot_number", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("vehicle_number", sa.String(50)),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column(
            "status",
            postgresql.ENUM("posted", "reversed", name="delivery_status_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("performed_by", sa.String(9), nullable=False),
        sa.Column("reversed_by", sa.String(9)),
        sa.Column("reversal_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["sales_order_item_id"], ["sales_order_items.id"]),
        sa.ForeignKeyConstraint(["sales_order_number"], ["sales_orders.sales_order_number"]),
        sa.ForeignKeyConstraint(["product_code"], ["products.code"]),
        sa.ForeignKeyConstraint(["lot_id"], ["product_lots.id"]),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reversed_by"], ["users.id"]),
    )


def downgrade() -> None:
    op.drop_table("deliveries")
    op.drop_table("finish_good_receipts")
    op.drop_table("bill_of_material_items")
    op.drop_table("daily_delivery_sequences")
    op.drop_table("daily_finish_good_sequences")
