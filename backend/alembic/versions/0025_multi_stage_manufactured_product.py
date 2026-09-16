"""add multi-stage manufactured product category

Revision ID: 0025
Revises: 0024
"""

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL enum values are intentionally additive: existing product
    # categories and historical transactions must remain unchanged. PostgreSQL
    # requires ADD VALUE to be committed before a later migration can query it.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE product_category_enum ADD VALUE IF NOT EXISTS 'multi_stage_manufactured'")


def downgrade() -> None:
    # PostgreSQL cannot safely remove an enum value while production data may
    # reference it. Keeping it is backwards-compatible and preserves history.
    pass
