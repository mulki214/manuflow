"""add production WIP executions

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_production_sequences",
        sa.Column("sequence_date", sa.Date(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("sequence_date"),
    )
    op.create_table(
        "production_executions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("production_number", sa.String(length=22), nullable=False),
        sa.Column("process_date", sa.Date(), nullable=False),
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
        sa.Column("after_process_code", sa.String(length=20), nullable=True),
        sa.Column("after_process_name", sa.String(length=150), nullable=True),
        sa.Column("machine_code", sa.String(length=15), nullable=True),
        sa.Column("machine_name", sa.String(length=200), nullable=True),
        sa.Column("processing_quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("good_quantity", sa.Numeric(20, 3), server_default="0", nullable=False),
        sa.Column("repair_quantity", sa.Numeric(20, 3), server_default="0", nullable=False),
        sa.Column("ng_quantity", sa.Numeric(20, 3), server_default="0", nullable=False),
        sa.Column("output_product_code", sa.String(length=15), nullable=True),
        sa.Column("output_unit", sa.String(length=10), nullable=True),
        sa.Column("repair_process_code", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("performed_by", sa.String(length=9), nullable=False),
        sa.Column("performed_by_name", sa.String(length=201), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["after_process_code"], ["wip_processes.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["before_process_code"], ["wip_processes.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_id"], ["wip_lot_jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["machine_code"], ["machines.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["output_product_code"], ["products.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plant_code"], ["plants.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_code"], ["products.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["repair_process_code"], ["wip_processes.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("production_number"),
    )
    for column in ("production_number", "process_date", "job_id", "lot_number", "lot_segment_code", "plant_code"):
        op.create_index(op.f(f"ix_production_executions_{column}"), "production_executions", [column])

    op.drop_constraint("wip_lot_jobs_source_transfer_number_key", "wip_lot_jobs", type_="unique")
    op.create_index(
        op.f("ix_wip_lot_jobs_source_transfer_number"),
        "wip_lot_jobs",
        ["source_transfer_number"],
        unique=False,
    )
    op.add_column("wip_lot_jobs", sa.Column("production_execution_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_wip_lot_jobs_production_execution_id",
        "wip_lot_jobs",
        "production_executions",
        ["production_execution_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_wip_lot_jobs_production_execution_id"),
        "wip_lot_jobs",
        ["production_execution_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_wip_lot_jobs_production_execution_id"), table_name="wip_lot_jobs")
    op.drop_constraint("fk_wip_lot_jobs_production_execution_id", "wip_lot_jobs", type_="foreignkey")
    op.drop_column("wip_lot_jobs", "production_execution_id")
    op.drop_index(op.f("ix_wip_lot_jobs_source_transfer_number"), table_name="wip_lot_jobs")
    op.create_unique_constraint(
        "wip_lot_jobs_source_transfer_number_key",
        "wip_lot_jobs",
        ["source_transfer_number"],
    )
    for column in ("plant_code", "lot_segment_code", "lot_number", "job_id", "process_date", "production_number"):
        op.drop_index(op.f(f"ix_production_executions_{column}"), table_name="production_executions")
    op.drop_table("production_executions")
    op.drop_table("daily_production_sequences")
