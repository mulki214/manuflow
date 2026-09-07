"""backfill sales order material allocations from active bom

Revision ID: 0020
Revises: 0019
"""

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO sales_order_material_allocations
            (sales_order_item_id, material_product_code, required_quantity, received_quantity, unit)
        SELECT soi.id, bom.material_product_code, soi.quantity_grams * bom.quantity, 0, bom.unit
        FROM sales_order_items AS soi
        JOIN bill_of_material_items AS bom
          ON bom.finished_product_code = soi.product_code
         AND bom.is_active = true
        ON CONFLICT (sales_order_item_id, material_product_code) DO NOTHING
        """
    )


def downgrade() -> None:
    # Backfilled rows are intentionally retained to avoid deleting material history.
    pass
