"""add finish good reversal metadata

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("finish_good_receipts", sa.Column("reversed_by", sa.String(9), nullable=True))
    op.add_column("finish_good_receipts", sa.Column("reversal_reason", sa.Text(), nullable=True))
    op.add_column("finish_good_receipts", sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_finish_good_receipts_reversed_by_users",
        "finish_good_receipts",
        "users",
        ["reversed_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_finish_good_receipts_reversed_by_users", "finish_good_receipts", type_="foreignkey")
    op.drop_column("finish_good_receipts", "reversed_at")
    op.drop_column("finish_good_receipts", "reversal_reason")
    op.drop_column("finish_good_receipts", "reversed_by")
