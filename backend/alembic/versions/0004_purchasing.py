"""Add purchasing authorization department and purchase orders."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    purchase_order_status = sa.Enum(
        "waiting_review", "approved", "rejected", name="purchase_order_status_enum"
    )

    op.execute(
        "INSERT INTO departments (code, name, workflow_status) "
        "VALUES ('PURCHASING', 'Purchasing', 'submitted') "
        "ON CONFLICT (code) DO NOTHING"
    )

    op.create_table(
        "daily_purchase_order_sequences",
        sa.Column("sequence_date", sa.Date(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("sequence_date"),
    )
    op.create_table(
        "purchase_orders",
        sa.Column("po_number", sa.String(length=20), nullable=False),
        sa.Column("po_date", sa.Date(), nullable=False),
        sa.Column("supplier_code", sa.String(length=15), nullable=False),
        sa.Column("supplier_name", sa.String(length=200), nullable=False),
        sa.Column("supplier_address", sa.Text(), nullable=False),
        sa.Column("supplier_phone", sa.String(length=32), nullable=False),
        sa.Column("supplier_contact_person", sa.String(length=150), nullable=False),
        sa.Column("quotation_reference", sa.String(length=100), nullable=True),
        sa.Column("quotation_date", sa.Date(), nullable=True),
        sa.Column("requested_delivery_date", sa.Date(), nullable=False),
        sa.Column("delivery_plant_code", sa.String(length=5), nullable=False),
        sa.Column("delivery_plant_name", sa.String(length=150), nullable=False),
        sa.Column("delivery_address", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("payment_terms_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("payment_due_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="IDR", nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(precision=20, scale=2), server_default="0", nullable=False),
        sa.Column("ppn_rate", sa.Numeric(precision=6, scale=3), server_default="0", nullable=False),
        sa.Column("ppn_amount", sa.Numeric(precision=20, scale=2), server_default="0", nullable=False),
        sa.Column("pph23_rate", sa.Numeric(precision=6, scale=3), server_default="0", nullable=False),
        sa.Column("pph23_amount", sa.Numeric(precision=20, scale=2), server_default="0", nullable=False),
        sa.Column("grand_total", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("status", purchase_order_status, server_default="waiting_review", nullable=False),
        sa.Column("department_code", sa.String(length=15), nullable=False),
        sa.Column("created_by", sa.String(length=9), nullable=False),
        sa.Column("reviewed_by", sa.String(length=9), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["delivery_plant_code"], ["plants.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_code"], ["departments.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supplier_code"], ["corporations.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("po_number"),
    )
    for column in ("po_date", "supplier_code", "requested_delivery_date", "delivery_plant_code", "status", "department_code"):
        op.create_index(op.f(f"ix_purchase_orders_{column}"), "purchase_orders", [column], unique=False)

    op.create_table(
        "purchase_order_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("purchase_order_number", sa.String(length=20), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(length=15), nullable=False),
        sa.Column("part_name", sa.String(length=200), nullable=False),
        sa.Column("part_no", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity_grams", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("unit", sa.String(length=10), server_default="gram", nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("remark", sa.Text(), server_default="", nullable=False),
        sa.ForeignKeyConstraint(["product_code"], ["products.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["purchase_order_number"], ["purchase_orders.po_number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("purchase_order_number", "line_number", name="uq_purchase_order_line_number"),
        sa.UniqueConstraint("purchase_order_number", "product_code", name="uq_purchase_order_product"),
    )
    op.create_index(
        op.f("ix_purchase_order_items_purchase_order_number"),
        "purchase_order_items",
        ["purchase_order_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_purchase_order_items_product_code"), "purchase_order_items", ["product_code"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_purchase_order_items_product_code"), table_name="purchase_order_items")
    op.drop_index(op.f("ix_purchase_order_items_purchase_order_number"), table_name="purchase_order_items")
    op.drop_table("purchase_order_items")
    for column in ("department_code", "status", "delivery_plant_code", "requested_delivery_date", "supplier_code", "po_date"):
        op.drop_index(op.f(f"ix_purchase_orders_{column}"), table_name="purchase_orders")
    op.drop_table("purchase_orders")
    op.drop_table("daily_purchase_order_sequences")
    op.execute("DELETE FROM departments WHERE code = 'PURCHASING' AND pic_user_id IS NULL AND head_user_id IS NULL")
    sa.Enum(name="purchase_order_status_enum").drop(op.get_bind())
