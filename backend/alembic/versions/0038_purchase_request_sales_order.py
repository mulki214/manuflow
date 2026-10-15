"""link purchase requests and generated purchase orders to sales orders

Revision ID: 0038_pr_so_link
Revises: 0037_so_subcontracting
"""

import sqlalchemy as sa

from alembic import op

revision = "0038_pr_so_link"
down_revision = "0037_so_subcontracting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_requests",
        sa.Column("sales_order_number", sa.String(length=20), nullable=True),
    )
    op.create_index(
        "ix_purchase_requests_sales_order_number",
        "purchase_requests",
        ["sales_order_number"],
    )
    op.create_foreign_key(
        "fk_purchase_requests_sales_order_number_sales_orders",
        "purchase_requests",
        "sales_orders",
        ["sales_order_number"],
        ["sales_order_number"],
        ondelete="RESTRICT",
    )
    op.add_column(
        "purchase_request_items",
        sa.Column("sales_order_item_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_purchase_request_items_sales_order_item_id",
        "purchase_request_items",
        ["sales_order_item_id"],
    )
    op.create_foreign_key(
        "fk_purchase_request_items_sales_order_item_id_sales_order_items",
        "purchase_request_items",
        "sales_order_items",
        ["sales_order_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_purchase_request_items_sales_order_item_id_sales_order_items",
        "purchase_request_items",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_purchase_request_items_sales_order_item_id",
        table_name="purchase_request_items",
    )
    op.drop_column("purchase_request_items", "sales_order_item_id")
    op.drop_constraint(
        "fk_purchase_requests_sales_order_number_sales_orders",
        "purchase_requests",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_purchase_requests_sales_order_number",
        table_name="purchase_requests",
    )
    op.drop_column("purchase_requests", "sales_order_number")
