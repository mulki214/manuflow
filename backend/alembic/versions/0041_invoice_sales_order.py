"""associate each invoice with its selected Sales Order

Revision ID: 0041_invoice_sales_order
Revises: 0040_delivery_invoices
"""

import sqlalchemy as sa

from alembic import op

revision = "0041_invoice_sales_order"
down_revision = "0040_delivery_invoices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("invoices")}
    if "sales_order_number" in columns:
        return

    op.add_column("invoices", sa.Column("sales_order_number", sa.String(20), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE invoices AS invoice
            SET sales_order_number = (
                SELECT item.sales_order_number
                FROM invoice_items AS item
                WHERE item.invoice_number = invoice.invoice_number
                ORDER BY item.line_number
                LIMIT 1
            )
            """
        )
    )
    op.alter_column("invoices", "sales_order_number", existing_type=sa.String(20), nullable=False)
    op.create_foreign_key(
        "fk_invoices_sales_order_number_sales_orders",
        "invoices",
        "sales_orders",
        ["sales_order_number"],
        ["sales_order_number"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_invoices_sales_order_number", "invoices", ["sales_order_number"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("invoices")}
    if "sales_order_number" not in columns:
        return
    indexes = {index["name"] for index in inspector.get_indexes("invoices")}
    if "ix_invoices_sales_order_number" in indexes:
        op.drop_index("ix_invoices_sales_order_number", table_name="invoices")
    foreign_keys = {foreign_key["name"] for foreign_key in inspector.get_foreign_keys("invoices")}
    if "fk_invoices_sales_order_number_sales_orders" in foreign_keys:
        op.drop_constraint("fk_invoices_sales_order_number_sales_orders", "invoices", type_="foreignkey")
    op.drop_column("invoices", "sales_order_number")
