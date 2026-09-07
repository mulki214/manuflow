"""add quality inspections and finish-good queue

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE wip_lot_status_enum ADD VALUE IF NOT EXISTS 'awaiting_finish_goods'")
    op.execute(
        "INSERT INTO departments (code, name, workflow_status) "
        "VALUES ('QUALITY', 'Quality', 'submitted') ON CONFLICT (code) DO NOTHING"
    )
    op.create_table(
        "daily_quality_sequences",
        sa.Column("sequence_date", sa.Date(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("sequence_date"),
    )
    op.create_table(
        "quality_inspections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quality_number", sa.String(length=22), nullable=False),
        sa.Column("inspection_date", sa.Date(), nullable=False),
        sa.Column("shift", sa.String(length=20), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(length=15), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("lot_number", sa.String(length=100), nullable=False),
        sa.Column("lot_segment_code", sa.String(length=40), nullable=False),
        sa.Column("plant_code", sa.String(length=5), nullable=False),
        sa.Column("unit", sa.String(length=10), nullable=False),
        sa.Column("before_process_code", sa.String(length=20), nullable=False),
        sa.Column("before_process_name", sa.String(length=150), nullable=False),
        sa.Column("inspection_quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("pass_quantity", sa.Numeric(20, 3), server_default="0", nullable=False),
        sa.Column("repair_quantity", sa.Numeric(20, 3), server_default="0", nullable=False),
        sa.Column("ng_quantity", sa.Numeric(20, 3), server_default="0", nullable=False),
        sa.Column("repair_process_code", sa.String(length=20), nullable=True),
        sa.Column("problem", sa.Text(), server_default="", nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("performed_by", sa.String(length=9), nullable=False),
        sa.Column("performed_by_name", sa.String(length=201), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["before_process_code"], ["wip_processes.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_id"], ["wip_lot_jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plant_code"], ["plants.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_code"], ["products.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["repair_process_code"], ["wip_processes.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quality_number"),
    )
    for column in ("quality_number", "inspection_date", "job_id", "lot_number", "lot_segment_code", "plant_code"):
        op.create_index(op.f(f"ix_quality_inspections_{column}"), "quality_inspections", [column])


def downgrade() -> None:
    for column in ("plant_code", "lot_segment_code", "lot_number", "job_id", "inspection_date", "quality_number"):
        op.drop_index(op.f(f"ix_quality_inspections_{column}"), table_name="quality_inspections")
    op.drop_table("quality_inspections")
    op.drop_table("daily_quality_sequences")
    # PostgreSQL enum values cannot be safely removed in-place.
