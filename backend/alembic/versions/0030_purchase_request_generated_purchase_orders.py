"""link purchase requests to automatically generated purchase orders

Revision ID: 0030
Revises: 0029
"""

from alembic import op
import sqlalchemy as sa


revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("purchase_requests", sa.Column("requested_delivery_date", sa.Date(), nullable=True))
    op.add_column("purchase_requests", sa.Column("delivery_plant_code", sa.String(5), nullable=True))
    op.create_foreign_key(
        "fk_purchase_requests_delivery_plant_code",
        "purchase_requests",
        "plants",
        ["delivery_plant_code"],
        ["code"],
        ondelete="RESTRICT",
    )
    op.add_column("purchase_request_items", sa.Column("purchase_order_number", sa.String(20), nullable=True))
    op.create_foreign_key(
        "fk_purchase_request_items_purchase_order_number",
        "purchase_request_items",
        "purchase_orders",
        ["purchase_order_number"],
        ["po_number"],
        ondelete="SET NULL",
    )
    op.create_index("ix_purchase_request_items_purchase_order_number", "purchase_request_items", ["purchase_order_number"])


def downgrade() -> None:
    op.drop_index("ix_purchase_request_items_purchase_order_number", table_name="purchase_request_items")
    op.drop_constraint("fk_purchase_request_items_purchase_order_number", "purchase_request_items", type_="foreignkey")
    op.drop_column("purchase_request_items", "purchase_order_number")
    op.drop_constraint("fk_purchase_requests_delivery_plant_code", "purchase_requests", type_="foreignkey")
    op.drop_column("purchase_requests", "delivery_plant_code")
    op.drop_column("purchase_requests", "requested_delivery_date")
