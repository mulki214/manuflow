"""backfill missing SO material allocations using active BOM leaves

Revision ID: 0024
Revises: 0023
"""

from collections import defaultdict
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Repair legacy approved SO items created before allocation support.

    Only items without *any* allocation are considered, so existing receiving
    history and quantities remain untouched. Active BOMs are resolved to leaf
    materials, matching the allocation logic used for newly created SOs.
    """
    bind = op.get_bind()
    bom_rows = bind.execute(
        sa.text(
            "SELECT finished_product_code, material_product_code, quantity, unit "
            "FROM bill_of_material_items WHERE is_active = true"
        )
    ).mappings()
    by_finished: dict[str, list[dict]] = defaultdict(list)
    for row in bom_rows:
        by_finished[row["finished_product_code"]].append(dict(row))

    items = bind.execute(
        sa.text(
            """
            SELECT soi.id, soi.product_code, soi.quantity_grams
            FROM sales_order_items soi
            JOIN sales_orders so ON so.sales_order_number = soi.sales_order_number
            WHERE so.status = 'approved'
              AND so.fulfillment_status = 'open'
              AND EXISTS (
                  SELECT 1 FROM bill_of_material_items bom
                  WHERE bom.finished_product_code = soi.product_code
                    AND bom.is_active = true
              )
              AND NOT EXISTS (
                  SELECT 1 FROM sales_order_material_allocations allocation
                  WHERE allocation.sales_order_item_id = soi.id
              )
            """
        )
    ).mappings()

    def leaves(
        code: str,
        quantity: Decimal,
        unit: str | None = None,
        ancestry: tuple[str, ...] = (),
    ) -> dict[str, tuple[Decimal, str]]:
        if code in ancestry:
            raise RuntimeError(f"Circular active BOM while backfilling {code}")
        components = by_finished.get(code, [])
        if not components:
            return {code: (quantity, unit or "")}
        result: dict[str, tuple[Decimal, str]] = {}
        for component in components:
            child_quantity = quantity * Decimal(component["quantity"])
            for material, (required, unit) in leaves(
                component["material_product_code"], child_quantity, component["unit"], (*ancestry, code)
            ).items():
                previous = result.get(material)
                if previous and previous[1] != unit:
                    raise RuntimeError(f"Inconsistent units for material {material}")
                result[material] = ((previous[0] if previous else Decimal("0")) + required, unit)
        return result

    insert = sa.text(
        """
        INSERT INTO sales_order_material_allocations
            (sales_order_item_id, material_product_code, required_quantity, received_quantity, unit)
        VALUES (:item_id, :material_code, :required_quantity, 0, :unit)
        ON CONFLICT (sales_order_item_id, material_product_code) DO NOTHING
        """
    )
    for item in items:
        for material_code, (required_quantity, unit) in leaves(
            item["product_code"], Decimal(item["quantity_grams"])
        ).items():
            bind.execute(
                insert,
                {
                    "item_id": item["id"],
                    "material_code": material_code,
                    "required_quantity": required_quantity,
                    "unit": unit,
                },
            )


def downgrade() -> None:
    # Backfilled allocation rows are retained to preserve receiving history.
    pass
