"""add product supply source

Revision ID: 0023
Revises: 0022
"""

import sqlalchemy as sa

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    supply_source = sa.Enum("external_supplier", "manufactured_internally", name="product_supply_source_enum")
    supply_source.create(bind, checkfirst=True)
    op.add_column(
        "products",
        sa.Column("supply_source", supply_source, nullable=False, server_default="external_supplier"),
    )
    op.create_index("ix_products_supply_source", "products", ["supply_source"], unique=False)
    op.alter_column("products", "supplier_code", existing_type=sa.String(length=15), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE products SET supplier_code = customer_code WHERE supplier_code IS NULL")
    op.alter_column("products", "supplier_code", existing_type=sa.String(length=15), nullable=False)
    op.drop_index("ix_products_supply_source", table_name="products")
    op.drop_column("products", "supply_source")
    sa.Enum(name="product_supply_source_enum").drop(op.get_bind(), checkfirst=True)
