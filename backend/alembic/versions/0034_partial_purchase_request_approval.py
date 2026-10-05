"""support partial purchase request approval

Revision ID: 0034_partial_pr_approval
Revises: 0033_stock_rebalancing
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0034_partial_pr_approval"
down_revision = "0033_stock_rebalancing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE purchase_request_status_enum ADD VALUE IF NOT EXISTS 'partially_approved'")
    op.execute("DO $$ BEGIN CREATE TYPE purchase_request_item_approval_status_enum AS ENUM ('pending', 'approved', 'rejected'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    approval_status = postgresql.ENUM(name="purchase_request_item_approval_status_enum", create_type=False)
    op.add_column("purchase_request_items", sa.Column("approval_status", approval_status, nullable=False, server_default="pending"))
    op.add_column("purchase_request_items", sa.Column("approved_quantity", sa.Numeric(14, 3), nullable=True))
    op.add_column("purchase_request_items", sa.Column("review_reason", sa.Text(), nullable=True))
    op.add_column("purchase_request_items", sa.Column("reviewed_by", sa.String(36), nullable=True))
    op.add_column("purchase_request_items", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_purchase_request_items_reviewed_by", "purchase_request_items", "users", ["reviewed_by"], ["id"], ondelete="SET NULL")
    op.create_index("ix_purchase_request_items_approval_status", "purchase_request_items", ["approval_status"])
    # Preserve a truthful line-level audit view for PRs reviewed before this feature existed.
    op.execute("""
        UPDATE purchase_request_items AS item
        SET approval_status = CASE request.status
                WHEN 'approved' THEN 'approved'::purchase_request_item_approval_status_enum
                WHEN 'rejected' THEN 'rejected'::purchase_request_item_approval_status_enum
                ELSE 'pending'::purchase_request_item_approval_status_enum
            END,
            approved_quantity = CASE
                WHEN request.status = 'approved' THEN item.quantity
                WHEN request.status = 'rejected' THEN 0
                ELSE NULL
            END,
            review_reason = CASE WHEN request.status = 'rejected' THEN request.rejection_reason ELSE NULL END,
            reviewed_by = request.reviewed_by,
            reviewed_at = request.reviewed_at
        FROM purchase_requests AS request
        WHERE request.request_number = item.request_number
          AND request.status IN ('approved', 'rejected')
    """)


def downgrade() -> None:
    op.drop_index("ix_purchase_request_items_approval_status", table_name="purchase_request_items")
    op.drop_constraint("fk_purchase_request_items_reviewed_by", "purchase_request_items", type_="foreignkey")
    op.drop_column("purchase_request_items", "reviewed_at")
    op.drop_column("purchase_request_items", "reviewed_by")
    op.drop_column("purchase_request_items", "review_reason")
    op.drop_column("purchase_request_items", "approved_quantity")
    op.drop_column("purchase_request_items", "approval_status")
    op.execute("DROP TYPE purchase_request_item_approval_status_enum")
    # PostgreSQL enum labels are retained to protect existing historical records.
