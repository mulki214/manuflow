"""Allow Purchase Requests to contain free-text products.

Revision ID: 0047_pr_free_text
Revises: 0046_rev_receiving_so_ref
"""

import sqlalchemy as sa

from alembic import op

revision = "0047_pr_free_text"
down_revision = "0046_rev_receiving_so_ref"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_requests",
        sa.Column("request_type", sa.String(length=20), server_default="master_data", nullable=False),
    )
    op.alter_column("purchase_request_items", "product_code", existing_type=sa.String(length=30), nullable=True)


def downgrade() -> None:
    op.alter_column("purchase_request_items", "product_code", existing_type=sa.String(length=30), nullable=False)
    op.drop_column("purchase_requests", "request_type")
