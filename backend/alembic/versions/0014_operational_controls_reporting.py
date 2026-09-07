"""add operational controls, repair routes, and reporting fields

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transportations", sa.Column("brand_name", sa.String(100), nullable=True))
    op.add_column("transportations", sa.Column("manufacturing_year", sa.Integer(), nullable=True))
    op.alter_column("transportations", "driver_name", existing_type=sa.String(150), nullable=True)

    op.add_column("deliveries", sa.Column("transportation_code", sa.String(15), nullable=True))
    op.add_column("deliveries", sa.Column("driver_name", sa.String(150), nullable=True))
    op.create_foreign_key(
        "fk_deliveries_transportation", "deliveries", "transportations", ["transportation_code"], ["code"]
    )

    op.create_table(
        "product_process_standards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_code", sa.String(15), sa.ForeignKey("products.code", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "process_code", sa.String(20), sa.ForeignKey("wip_processes.code", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("machine_code", sa.String(15), sa.ForeignKey("machines.code", ondelete="SET NULL"), nullable=True),
        sa.Column("working_hours", sa.Numeric(10, 3), nullable=False),
        sa.Column("expected_output_quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("output_unit", sa.String(10), nullable=False),
        sa.Column("target_cycle_time_seconds", sa.Numeric(14, 3), nullable=True),
        sa.Column("maximum_ng_quantity", sa.Numeric(20, 3), nullable=True),
        sa.Column("maximum_ng_percent", sa.Numeric(7, 4), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("product_code", "process_code", "machine_code", name="uq_product_process_standard"),
    )
    for name in ("product_code", "process_code", "machine_code"):
        op.create_index(f"ix_product_process_standards_{name}", "product_process_standards", [name])

    op.create_table(
        "repair_routes",
        sa.Column("code", sa.String(20), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("product_code", sa.String(15), sa.ForeignKey("products.code", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "source_process_code",
            sa.String(20),
            sa.ForeignKey("wip_processes.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "return_process_code",
            sa.String(20),
            sa.ForeignKey("wip_processes.code", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by", sa.String(9), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "repair_route_steps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("route_code", sa.String(20), sa.ForeignKey("repair_routes.code", ondelete="CASCADE"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column(
            "process_code", sa.String(20), sa.ForeignKey("wip_processes.code", ondelete="RESTRICT"), nullable=False
        ),
        sa.UniqueConstraint("route_code", "step_order", name="uq_repair_route_step_order"),
    )

    op.add_column("wip_lot_jobs", sa.Column("repair_route_code", sa.String(20), nullable=True))
    op.add_column("wip_lot_jobs", sa.Column("repair_step_order", sa.Integer(), nullable=True))
    op.add_column("wip_lot_jobs", sa.Column("repair_return_process_code", sa.String(20), nullable=True))
    op.create_foreign_key("fk_wip_job_repair_route", "wip_lot_jobs", "repair_routes", ["repair_route_code"], ["code"])
    op.create_foreign_key(
        "fk_wip_job_repair_return_process",
        "wip_lot_jobs",
        "wip_processes",
        ["repair_return_process_code"],
        ["code"],
    )

    op.add_column("production_executions", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("production_executions", sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "production_executions", sa.Column("break_duration_minutes", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("production_executions", sa.Column("cycle_time_seconds", sa.Numeric(14, 3), nullable=True))
    op.add_column("production_executions", sa.Column("observed_cycle_time_seconds", sa.Numeric(14, 3), nullable=True))
    op.add_column(
        "production_executions", sa.Column("ng_limit_exceeded", sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.add_column("production_executions", sa.Column("ng_override_by", sa.String(9), nullable=True))
    op.add_column("production_executions", sa.Column("ng_override_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("production_executions", sa.Column("ng_override_reason", sa.Text(), nullable=True))
    op.add_column("production_executions", sa.Column("repair_route_code", sa.String(20), nullable=True))
    op.create_foreign_key(
        "fk_production_ng_override_user", "production_executions", "users", ["ng_override_by"], ["id"]
    )
    op.create_foreign_key(
        "fk_production_repair_route", "production_executions", "repair_routes", ["repair_route_code"], ["code"]
    )

    op.add_column(
        "quality_inspections", sa.Column("ng_limit_exceeded", sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.add_column("quality_inspections", sa.Column("ng_override_by", sa.String(9), nullable=True))
    op.add_column("quality_inspections", sa.Column("ng_override_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("quality_inspections", sa.Column("ng_override_reason", sa.Text(), nullable=True))
    op.add_column("quality_inspections", sa.Column("repair_route_code", sa.String(20), nullable=True))
    op.create_foreign_key("fk_quality_ng_override_user", "quality_inspections", "users", ["ng_override_by"], ["id"])
    op.create_foreign_key(
        "fk_quality_repair_route", "quality_inspections", "repair_routes", ["repair_route_code"], ["code"]
    )

    op.create_table(
        "consumable_dispositions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "production_execution_id",
            sa.Integer(),
            sa.ForeignKey("production_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_lot_id", sa.Integer(), sa.ForeignKey("product_lots.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("consumed_quantity", sa.Numeric(20, 3), server_default="0", nullable=False),
        sa.Column("waste_quantity", sa.Numeric(20, 3), server_default="0", nullable=False),
        sa.Column("scrap_quantity", sa.Numeric(20, 3), server_default="0", nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column(
            "scrap_storage_location_code",
            sa.String(15),
            sa.ForeignKey("storage_locations.code", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("performed_by", sa.String(9), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("consumable_dispositions")
    op.drop_constraint("fk_quality_repair_route", "quality_inspections", type_="foreignkey")
    op.drop_constraint("fk_quality_ng_override_user", "quality_inspections", type_="foreignkey")
    op.drop_constraint("fk_production_repair_route", "production_executions", type_="foreignkey")
    op.drop_constraint("fk_production_ng_override_user", "production_executions", type_="foreignkey")
    for table in ("quality_inspections", "production_executions"):
        for column in (
            "repair_route_code",
            "ng_override_reason",
            "ng_override_at",
            "ng_override_by",
            "ng_limit_exceeded",
        ):
            op.drop_column(table, column)
    for column in (
        "observed_cycle_time_seconds",
        "cycle_time_seconds",
        "break_duration_minutes",
        "ended_at",
        "started_at",
    ):
        op.drop_column("production_executions", column)
    op.drop_constraint("fk_wip_job_repair_return_process", "wip_lot_jobs", type_="foreignkey")
    op.drop_constraint("fk_wip_job_repair_route", "wip_lot_jobs", type_="foreignkey")
    op.drop_column("wip_lot_jobs", "repair_return_process_code")
    op.drop_column("wip_lot_jobs", "repair_step_order")
    op.drop_column("wip_lot_jobs", "repair_route_code")
    op.drop_table("repair_route_steps")
    op.drop_table("repair_routes")
    op.drop_table("product_process_standards")
    op.drop_constraint("fk_deliveries_transportation", "deliveries", type_="foreignkey")
    op.drop_column("deliveries", "driver_name")
    op.drop_column("deliveries", "transportation_code")
    op.alter_column("transportations", "driver_name", existing_type=sa.String(150), nullable=False)
    op.drop_column("transportations", "manufacturing_year")
    op.drop_column("transportations", "brand_name")
