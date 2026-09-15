"""backfill customer-supplied multi-stage SO receiving allocations

Revision ID: 0026
Revises: 0025
"""

import sqlalchemy as sa

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Make existing approved multi-stage SOs available in Receiving.

    Only SO items with no allocation are inserted. This avoids changing a
    receipt history or duplicating BOM allocations created before the product
    was classified as multi-stage.
    """
    op.execute(
        sa.text(
            """
            INSERT INTO sales_order_material_allocations
                (sales_order_item_id, material_product_code, required_quantity, received_quantity, unit)
            SELECT soi.id, soi.product_code, soi.quantity_grams, 0, soi.unit
            FROM sales_order_items AS soi
            JOIN sales_orders AS so ON so.sales_order_number = soi.sales_order_number
            JOIN products AS product ON product.code = soi.product_code
            WHERE so.status = 'approved'
              AND so.fulfillment_status = 'open'
              AND product.category = 'multi_stage_manufactured'
              AND NOT EXISTS (
                  SELECT 1
                  FROM sales_order_material_allocations AS allocation
                  WHERE allocation.sales_order_item_id = soi.id
              )
            """
        )
    )


def downgrade() -> None:
    # Retain the allocation as an audit record; it may already have Receiving
    # transactions referencing it.
    pass
