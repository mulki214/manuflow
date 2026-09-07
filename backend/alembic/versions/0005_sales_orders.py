"""Add Sales department and sales orders."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    sales_order_status = sa.Enum(
        "waiting_review", "approved", "rejected", name="sales_order_status_enum"
    )
    sales_order_type = sa.Enum(
        "regular", "sample", "trial", "replacement", name="sales_order_type_enum"
    )
    op.execute(
        "INSERT INTO departments (code, name, workflow_status) "
        "VALUES ('SALES', 'Sales', 'submitted') ON CONFLICT (code) DO NOTHING"
    )
    op.create_table(
        "daily_sales_order_sequences",
        sa.Column("sequence_date", sa.Date(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("sequence_date"),
    )
    op.create_table(
        "sales_orders",
        sa.Column("sales_order_number", sa.String(length=20), nullable=False),
        sa.Column("po_receipt_date", sa.Date(), nullable=False),
        sa.Column("customer_po_date", sa.Date(), nullable=False),
        sa.Column("customer_po_number", sa.String(length=100), nullable=False),
        sa.Column("customer_code", sa.String(length=15), nullable=False),
        sa.Column("customer_name", sa.String(length=200), nullable=False),
        sa.Column("bill_to_address", sa.Text(), nullable=False),
        sa.Column("bill_to_phone", sa.String(length=32), nullable=False),
        sa.Column("ship_to_name", sa.String(length=200), nullable=False),
        sa.Column("ship_to_address", sa.Text(), nullable=False),
        sa.Column("ship_to_contact_person", sa.String(length=150), nullable=False),
        sa.Column("ship_to_phone", sa.String(length=32), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("order_type", sales_order_type, nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="IDR", nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("grand_total", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("status", sales_order_status, server_default="waiting_review", nullable=False),
        sa.Column("department_code", sa.String(length=15), nullable=False),
        sa.Column("created_by", sa.String(length=9), nullable=False),
        sa.Column("reviewed_by", sa.String(length=9), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_code"], ["corporations.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_code"], ["departments.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("sales_order_number"),
    )
    for column in (
        "po_receipt_date",
        "customer_po_date",
        "customer_po_number",
        "customer_code",
        "delivery_date",
        "order_type",
        "status",
        "department_code",
    ):
        op.create_index(op.f(f"ix_sales_orders_{column}"), "sales_orders", [column], unique=False)

    op.create_table(
        "sales_order_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sales_order_number", sa.String(length=20), nullable=False),
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
        sa.ForeignKeyConstraint(["sales_order_number"], ["sales_orders.sales_order_number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sales_order_number", "line_number", name="uq_sales_order_line_number"),
        sa.UniqueConstraint("sales_order_number", "product_code", name="uq_sales_order_product"),
    )
    op.create_index(
        op.f("ix_sales_order_items_sales_order_number"),
        "sales_order_items",
        ["sales_order_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sales_order_items_product_code"), "sales_order_items", ["product_code"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sales_order_items_product_code"), table_name="sales_order_items")
    op.drop_index(op.f("ix_sales_order_items_sales_order_number"), table_name="sales_order_items")
    op.drop_table("sales_order_items")
    for column in (
        "department_code",
        "status",
        "order_type",
        "delivery_date",
        "customer_code",
        "customer_po_number",
        "customer_po_date",
        "po_receipt_date",
    ):
        op.drop_index(op.f(f"ix_sales_orders_{column}"), table_name="sales_orders")
    op.drop_table("sales_orders")
    op.drop_table("daily_sales_order_sequences")
    op.execute("DELETE FROM departments WHERE code = 'SALES' AND pic_user_id IS NULL AND head_user_id IS NULL")
    sa.Enum(name="sales_order_type_enum").drop(op.get_bind())
    sa.Enum(name="sales_order_status_enum").drop(op.get_bind())
