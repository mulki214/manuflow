"""add sales invoices sourced from delivered quantities

Revision ID: 0040_delivery_invoices
Revises: 0039_bom_consumable_variance
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0040_delivery_invoices"
down_revision = "0039_bom_consumable_variance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    invoice_status = postgresql.ENUM("issued", "void", name="invoice_status_enum", create_type=False)
    invoice_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "daily_invoice_sequences",
        sa.Column("sequence_date", sa.Date(), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False),
    )
    op.create_table(
        "invoices",
        sa.Column("invoice_number", sa.String(20), primary_key=True),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "customer_code", sa.String(15), sa.ForeignKey("corporations.code", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("customer_address", sa.Text(), nullable=False),
        sa.Column("customer_phone", sa.String(32), nullable=False),
        sa.Column("customer_contact_person", sa.String(150), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("payment_terms", sa.Text(), nullable=False, server_default=""),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IDR"),
        sa.Column("subtotal", sa.Numeric(20, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("tax_label", sa.String(50), nullable=False, server_default="PPN"),
        sa.Column("tax_rate", sa.Numeric(6, 3), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("grand_total", sa.Numeric(20, 2), nullable=False),
        sa.Column("status", invoice_status, nullable=False, server_default="issued"),
        sa.Column("created_by", sa.String(9), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by_name", sa.String(201), nullable=False),
        sa.Column("voided_by", sa.String(9), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("voided_by_name", sa.String(201), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_invoices_invoice_date", "invoices", ["invoice_date"])
    op.create_index("ix_invoices_customer_code", "invoices", ["customer_code"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "invoice_number",
            sa.String(20),
            sa.ForeignKey("invoices.invoice_number", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column(
            "delivery_number",
            sa.String(22),
            sa.ForeignKey("deliveries.delivery_number", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "delivery_line_id", sa.Integer(), sa.ForeignKey("delivery_lines.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column(
            "sales_order_number",
            sa.String(20),
            sa.ForeignKey("sales_orders.sales_order_number", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "sales_order_item_id",
            sa.Integer(),
            sa.ForeignKey("sales_order_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("product_code", sa.String(15), sa.ForeignKey("products.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("part_name", sa.String(200), nullable=False),
        sa.Column("part_no", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("lot_number", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("unit_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("remark", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_invoice_items_invoice_number", "invoice_items", ["invoice_number"])
    op.create_index("ix_invoice_items_delivery_number", "invoice_items", ["delivery_number"])
    op.create_index("ix_invoice_items_delivery_line_id", "invoice_items", ["delivery_line_id"])
    op.create_index("ix_invoice_items_sales_order_number", "invoice_items", ["sales_order_number"])
    op.create_index("ix_invoice_items_sales_order_item_id", "invoice_items", ["sales_order_item_id"])


def downgrade() -> None:
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_table("daily_invoice_sequences")
    sa.Enum(name="invoice_status_enum").drop(op.get_bind(), checkfirst=True)
