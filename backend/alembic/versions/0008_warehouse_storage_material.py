"""Add Warehouse Storage Material transfers and WIP entry jobs."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    destination_type = postgresql.ENUM("wip", "finished_goods", name="warehouse_destination_type_enum")
    transfer_status = postgresql.ENUM("posted", "reversed", name="warehouse_transfer_status_enum")
    process_type = postgresql.ENUM("production", "quality", "repair", name="wip_process_type_enum")
    lot_status = postgresql.ENUM(
        "queued",
        "in_process",
        "awaiting_qc",
        "repair_required",
        "repair_in_process",
        "ng",
        "completed",
        "reversed",
        name="wip_lot_status_enum",
    )

    op.execute("ALTER TYPE inventory_movement_type_enum ADD VALUE IF NOT EXISTS 'warehouse_out'")
    op.execute("ALTER TYPE inventory_movement_type_enum ADD VALUE IF NOT EXISTS 'warehouse_in'")
    op.execute("ALTER TYPE inventory_movement_type_enum ADD VALUE IF NOT EXISTS 'warehouse_reversal'")

    op.create_table(
        "daily_warehouse_transfer_sequences",
        sa.Column("sequence_date", sa.Date(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("sequence_date"),
    )
    op.create_table(
        "wip_processes",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("process_type", process_type, nullable=False),
        sa.Column("plant_code", sa.String(length=5), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by", sa.String(length=9), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plant_code"], ["plants.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("code"),
    )
    for column in ("name", "process_type", "plant_code"):
        op.create_index(op.f(f"ix_wip_processes_{column}"), "wip_processes", [column])

    op.create_table(
        "warehouse_material_transfers",
        sa.Column("transfer_number", sa.String(length=20), nullable=False),
        sa.Column("transfer_date", sa.Date(), nullable=False),
        sa.Column("product_code", sa.String(length=15), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("lot_number", sa.String(length=100), nullable=False),
        sa.Column("quantity_grams", sa.Numeric(20, 3), nullable=False),
        sa.Column("unit", sa.String(length=10), nullable=False),
        sa.Column("plant_code", sa.String(length=5), nullable=False),
        sa.Column("plant_name", sa.String(length=150), nullable=False),
        sa.Column("source_lot_id", sa.Integer(), nullable=False),
        sa.Column("source_storage_code", sa.String(length=15), nullable=False),
        sa.Column("source_storage_name", sa.String(length=150), nullable=False),
        sa.Column("source_location_code", sa.String(length=15), nullable=False),
        sa.Column("source_location_name", sa.String(length=150), nullable=False),
        sa.Column("destination_type", destination_type, nullable=False),
        sa.Column("destination_process_code", sa.String(length=20), nullable=True),
        sa.Column("destination_process_name", sa.String(length=150), nullable=True),
        sa.Column("destination_storage_code", sa.String(length=15), nullable=True),
        sa.Column("destination_storage_name", sa.String(length=150), nullable=True),
        sa.Column("destination_location_code", sa.String(length=15), nullable=True),
        sa.Column("destination_location_name", sa.String(length=150), nullable=True),
        sa.Column("destination_lot_id", sa.Integer(), nullable=True),
        sa.Column("document_number", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("status", transfer_status, server_default="posted", nullable=False),
        sa.Column("performed_by", sa.String(length=9), nullable=False),
        sa.Column("performed_by_name", sa.String(length=201), nullable=False),
        sa.Column("reversed_by", sa.String(length=9), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["destination_location_code"], ["storage_locations.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["destination_lot_id"], ["product_lots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["destination_process_code"], ["wip_processes.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["destination_storage_code"], ["warehouse_storages.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plant_code"], ["plants.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_code"], ["products.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_location_code"], ["storage_locations.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_lot_id"], ["product_lots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_storage_code"], ["warehouse_storages.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("transfer_number"),
    )
    for column in (
        "transfer_date",
        "product_code",
        "lot_number",
        "plant_code",
        "source_lot_id",
        "destination_type",
        "destination_process_code",
        "document_number",
        "status",
    ):
        op.create_index(op.f(f"ix_warehouse_material_transfers_{column}"), "warehouse_material_transfers", [column])

    op.create_table(
        "wip_lot_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_transfer_number", sa.String(length=20), nullable=False),
        sa.Column("parent_job_id", sa.Integer(), nullable=True),
        sa.Column("process_code", sa.String(length=20), nullable=False),
        sa.Column("product_code", sa.String(length=15), nullable=False),
        sa.Column("lot_number", sa.String(length=100), nullable=False),
        sa.Column("lot_segment_code", sa.String(length=40), nullable=False),
        sa.Column("plant_code", sa.String(length=5), nullable=False),
        sa.Column("unit", sa.String(length=10), nullable=False),
        sa.Column("input_quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("current_quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("status", lot_status, server_default="queued", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["parent_job_id"], ["wip_lot_jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plant_code"], ["plants.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["process_code"], ["wip_processes.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_code"], ["products.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_transfer_number"], ["warehouse_material_transfers.transfer_number"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lot_segment_code"),
        sa.UniqueConstraint("source_transfer_number"),
    )
    for column in ("process_code", "product_code", "lot_number", "lot_segment_code", "plant_code", "status"):
        op.create_index(op.f(f"ix_wip_lot_jobs_{column}"), "wip_lot_jobs", [column])


def downgrade() -> None:
    for column in ("status", "plant_code", "lot_segment_code", "lot_number", "product_code", "process_code"):
        op.drop_index(op.f(f"ix_wip_lot_jobs_{column}"), table_name="wip_lot_jobs")
    op.drop_table("wip_lot_jobs")
    for column in (
        "status",
        "document_number",
        "destination_process_code",
        "destination_type",
        "source_lot_id",
        "plant_code",
        "lot_number",
        "product_code",
        "transfer_date",
    ):
        op.drop_index(op.f(f"ix_warehouse_material_transfers_{column}"), table_name="warehouse_material_transfers")
    op.drop_table("warehouse_material_transfers")
    for column in ("plant_code", "process_type", "name"):
        op.drop_index(op.f(f"ix_wip_processes_{column}"), table_name="wip_processes")
    op.drop_table("wip_processes")
    op.drop_table("daily_warehouse_transfer_sequences")
    sa.Enum(name="wip_lot_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="wip_process_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="warehouse_transfer_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="warehouse_destination_type_enum").drop(op.get_bind(), checkfirst=True)

