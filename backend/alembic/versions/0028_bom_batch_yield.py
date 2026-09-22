"""add BOM batch yield headers

Revision ID: 0028
Revises: 0027
"""

import sqlalchemy as sa

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bill_of_materials",
        sa.Column("finished_product_code", sa.String(length=15), nullable=False),
        sa.Column("output_quantity", sa.Numeric(20, 3), nullable=False, server_default="1"),
        sa.Column("output_unit", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["finished_product_code"], ["products.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("finished_product_code"),
    )
    # Preserve all existing BOM calculations: no historical output unit was stored,
    # so those headers remain in legacy one-output-unit mode.
    op.execute(
        """
        INSERT INTO bill_of_materials (finished_product_code, output_quantity)
        SELECT DISTINCT finished_product_code, 1
        FROM bill_of_material_items
        """
    )


def downgrade() -> None:
    op.drop_table("bill_of_materials")
