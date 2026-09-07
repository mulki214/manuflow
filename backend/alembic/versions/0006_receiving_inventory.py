"""Add Warehouse receiving and lot-based inventory ledger."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    receiving_status = sa.Enum("posted", "reversed", name="receiving_status_enum")
    movement_type = sa.Enum(
        "receiving_in", "receiving_reversal", "stock_out", name="inventory_movement_type_enum"
    )
    workflow_status = postgresql.ENUM(
        "submitted",
        name="workflow_status_enum",
        create_type=False,
    )
    op.execute(
        "INSERT INTO departments (code, name, workflow_status) "
        "VALUES ('WAREHOUSE', 'Warehouse', 'submitted') ON CONFLICT (code) DO NOTHING"
    )
    op.add_column(
        "products",
        sa.Column("current_stock_grams", sa.Numeric(precision=20, scale=3), server_default="0", nullable=False),
    )
    op.create_table(
        "daily_receiving_sequences",
        sa.Column("sequence_date", sa.Date(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("sequence_date"),
    )
    op.create_table(
        "storage_locations",
        sa.Column("code", sa.String(length=15), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("plant_code", sa.String(length=5), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("department_code", sa.String(length=15), nullable=True),
        sa.Column("created_by", sa.String(length=9), nullable=True),
        sa.Column("workflow_status", workflow_status, server_default="submitted", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["department_code"], ["departments.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plant_code"], ["plants.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("code"),
    )
    for column in ("name", "plant_code", "department_code"):
        op.create_index(op.f(f"ix_storage_locations_{column}"), "storage_locations", [column], unique=False)
    op.create_table(
        "product_lots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_code", sa.String(length=15), nullable=False),
        sa.Column("lot_number", sa.String(length=100), nullable=False),
        sa.Column("plant_code", sa.String(length=5), nullable=False),
        sa.Column("storage_location_code", sa.String(length=15), nullable=False),
        sa.Column("initial_quantity_grams", sa.Numeric(precision=20, scale=3), nullable=False),
        sa.Column("current_quantity_grams", sa.Numeric(precision=20, scale=3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["plant_code"], ["plants.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_code"], ["products.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["storage_location_code"], ["storage_locations.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_code", "lot_number", name="uq_product_lot"),
    )
    for column in ("product_code", "lot_number", "plant_code", "storage_location_code"):
        op.create_index(op.f(f"ix_product_lots_{column}"), "product_lots", [column], unique=False)
    op.create_table(
        "receivings",
        sa.Column("receipt_number", sa.String(length=21), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("product_code", sa.String(length=15), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("lot_number", sa.String(length=100), nullable=False),
        sa.Column("quantity_grams", sa.Numeric(precision=20, scale=3), nullable=False),
        sa.Column("unit", sa.String(length=10), server_default="gram", nullable=False),
        sa.Column("plant_code", sa.String(length=5), nullable=False),
        sa.Column("plant_name", sa.String(length=150), nullable=False),
        sa.Column("storage_location_code", sa.String(length=15), nullable=False),
        sa.Column("storage_location_name", sa.String(length=150), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("document_number", sa.String(length=100), nullable=True),
        sa.Column("po_number", sa.String(length=100), nullable=True),
        sa.Column("vehicle_number", sa.String(length=50), nullable=True),
        sa.Column("driver_name", sa.String(length=150), nullable=True),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("receiver_id", sa.String(length=9), nullable=False),
        sa.Column("receiver_name", sa.String(length=201), nullable=False),
        sa.Column("status", receiving_status, server_default="posted", nullable=False),
        sa.Column("reversed_by", sa.String(length=9), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["lot_id"], ["product_lots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plant_code"], ["plants.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_code"], ["products.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["receiver_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["storage_location_code"], ["storage_locations.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("receipt_number"),
        sa.UniqueConstraint("lot_id"),
    )
    for column in (
        "receipt_date", "product_code", "lot_number", "plant_code", "storage_location_code",
        "document_number", "po_number", "status",
    ):
        op.create_index(op.f(f"ix_receivings_{column}"), "receivings", [column], unique=False)
    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("movement_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("movement_type", movement_type, nullable=False),
        sa.Column("product_code", sa.String(length=15), nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("quantity_grams", sa.Numeric(precision=20, scale=3), nullable=False),
        sa.Column("product_stock_after_grams", sa.Numeric(precision=20, scale=3), nullable=False),
        sa.Column("lot_stock_after_grams", sa.Numeric(precision=20, scale=3), nullable=False),
        sa.Column("reference_type", sa.String(length=30), nullable=False),
        sa.Column("reference_number", sa.String(length=30), nullable=False),
        sa.Column("performed_by", sa.String(length=9), nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.ForeignKeyConstraint(["lot_id"], ["product_lots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_code"], ["products.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("movement_date", "movement_type", "product_code", "lot_id", "reference_number"):
        op.create_index(op.f(f"ix_inventory_movements_{column}"), "inventory_movements", [column], unique=False)


def downgrade() -> None:
    for column in ("reference_number", "lot_id", "product_code", "movement_type", "movement_date"):
        op.drop_index(op.f(f"ix_inventory_movements_{column}"), table_name="inventory_movements")
    op.drop_table("inventory_movements")
    for column in (
        "status",
        "po_number",
        "document_number",
        "storage_location_code",
        "plant_code",
        "lot_number",
        "product_code",
        "receipt_date",
    ):
        op.drop_index(op.f(f"ix_receivings_{column}"), table_name="receivings")
    op.drop_table("receivings")
    for column in ("storage_location_code", "plant_code", "lot_number", "product_code"):
        op.drop_index(op.f(f"ix_product_lots_{column}"), table_name="product_lots")
    op.drop_table("product_lots")
    for column in ("department_code", "plant_code", "name"):
        op.drop_index(op.f(f"ix_storage_locations_{column}"), table_name="storage_locations")
    op.drop_table("storage_locations")
    op.drop_table("daily_receiving_sequences")
    op.drop_column("products", "current_stock_grams")
    op.execute("DELETE FROM departments WHERE code='WAREHOUSE' AND pic_user_id IS NULL AND head_user_id IS NULL")
    sa.Enum(name="inventory_movement_type_enum").drop(op.get_bind())
    sa.Enum(name="receiving_status_enum").drop(op.get_bind())
