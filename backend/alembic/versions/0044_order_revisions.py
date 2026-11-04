"""add audited revisions for sales and purchase orders

Revision ID: 0044_order_revisions
Revises: 0043_qc_direct_receive
"""

import sqlalchemy as sa

from alembic import op

revision = "0044_order_revisions"
down_revision = "0043_qc_direct_receive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_type", sa.String(length=20), nullable=False),
        sa.Column("order_number", sa.String(length=20), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changed_by", sa.String(length=9), nullable=False),
        sa.Column("changed_by_name", sa.String(length=201), nullable=False),
        sa.Column("before_snapshot", sa.JSON(), nullable=False),
        sa.Column("after_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_type", "order_number", "revision_number", name="uq_order_revision_number"),
    )
    op.create_index("ix_order_revisions_order_type", "order_revisions", ["order_type"])
    op.create_index("ix_order_revisions_order_number", "order_revisions", ["order_number"])


def downgrade() -> None:
    op.drop_index("ix_order_revisions_order_number", table_name="order_revisions")
    op.drop_index("ix_order_revisions_order_type", table_name="order_revisions")
    op.drop_table("order_revisions")
