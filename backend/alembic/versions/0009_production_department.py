"""add Production department

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO departments (code, name, workflow_status) "
        "VALUES ('PRODUCTION', 'Production', 'submitted') "
        "ON CONFLICT (code) DO NOTHING"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM departments WHERE code='PRODUCTION' "
        "AND pic_user_id IS NULL AND head_user_id IS NULL"
    )
