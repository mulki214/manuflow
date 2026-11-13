"""Retain SO identifiers on receiving history independently of SO item links.

Revision ID: 0046_rev_receiving_so_ref
Revises: 0045_inter_plant_wip_transfers
"""

import sqlalchemy as sa

from alembic import op

revision = "0046_rev_receiving_so_ref"
down_revision = "0045_inter_plant_wip_transfers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("receivings", sa.Column("sales_order_number", sa.String(length=20), nullable=True))
    op.create_index("ix_receivings_sales_order_number", "receivings", ["sales_order_number"])
    op.execute(
        sa.text(
            """
            UPDATE receivings AS receiving
            SET sales_order_number = sales_order_item.sales_order_number
            FROM sales_order_items AS sales_order_item
            WHERE receiving.sales_order_item_id = sales_order_item.id
              AND receiving.sales_order_number IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_receivings_sales_order_number", table_name="receivings")
    op.drop_column("receivings", "sales_order_number")
