"""add sales order material allocations

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_order_material_allocations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "sales_order_item_id",
            sa.Integer(),
            sa.ForeignKey("sales_order_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "material_product_code", sa.String(30), sa.ForeignKey("products.code", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("required_quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("received_quantity", sa.Numeric(20, 3), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("sales_order_item_id", "material_product_code", name="uq_so_item_material"),
    )
    op.create_index(
        "ix_sales_order_material_allocations_sales_order_item_id",
        "sales_order_material_allocations",
        ["sales_order_item_id"],
    )
    op.create_index(
        "ix_sales_order_material_allocations_material_product_code",
        "sales_order_material_allocations",
        ["material_product_code"],
    )
    op.add_column("receivings", sa.Column("material_allocation_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_receivings_material_allocation",
        "receivings",
        "sales_order_material_allocations",
        ["material_allocation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_receivings_material_allocation_id", "receivings", ["material_allocation_id"])


def downgrade() -> None:
    op.drop_index("ix_receivings_material_allocation_id", table_name="receivings")
    op.drop_constraint("fk_receivings_material_allocation", "receivings", type_="foreignkey")
    op.drop_column("receivings", "material_allocation_id")
    op.drop_table("sales_order_material_allocations")
