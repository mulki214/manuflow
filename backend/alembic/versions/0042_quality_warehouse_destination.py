"""allow warehouse transfers directly into the quality queue

Revision ID: 0042_quality_destination
Revises: 0041_invoice_sales_order
"""

from alembic import op

revision = "0042_quality_destination"
down_revision = "0041_invoice_sales_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE warehouse_destination_type_enum ADD VALUE IF NOT EXISTS 'quality'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely while rows may reference them.
    pass
