"""Add multi PIC, unit-aware fulfillment, storage, and transportation."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    workflow_status = postgresql.ENUM("submitted", name="workflow_status_enum", create_type=False)
    fulfillment_status = postgresql.ENUM("open", "closed", name="fulfillment_status_enum", create_type=False)
    storage_type = postgresql.ENUM(
        "raw_material",
        "work_in_progress",
        "finished_goods",
        "general",
        name="storage_type_enum",
    )
    source_type = postgresql.ENUM("supplier", "customer", name="receiving_source_type_enum")
    fulfillment_status.create(op.get_bind(), checkfirst=True)
    source_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "department_pics",
        sa.Column("department_code", sa.String(length=15), nullable=False),
        sa.Column("user_id", sa.String(length=9), nullable=False),
        sa.ForeignKeyConstraint(["department_code"], ["departments.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("department_code", "user_id"),
    )
    op.execute(
        "INSERT INTO department_pics (department_code, user_id) "
        "SELECT code, pic_user_id FROM departments WHERE pic_user_id IS NOT NULL "
        "ON CONFLICT DO NOTHING"
    )

    op.create_table(
        "warehouse_storages",
        sa.Column("code", sa.String(length=15), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("storage_type", storage_type, nullable=False),
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
    for column in ("name", "storage_type", "plant_code", "department_code"):
        op.create_index(op.f(f"ix_warehouse_storages_{column}"), "warehouse_storages", [column])

    op.create_table(
        "transportations",
        sa.Column("code", sa.String(length=15), nullable=False),
        sa.Column("vehicle_number", sa.String(length=50), nullable=False),
        sa.Column("vehicle_type", sa.String(length=100), nullable=False),
        sa.Column("driver_name", sa.String(length=150), nullable=False),
        sa.Column("carrier_name", sa.String(length=200), nullable=False),
        sa.Column("capacity", sa.Numeric(14, 3), nullable=True),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("department_code", sa.String(length=15), nullable=True),
        sa.Column("created_by", sa.String(length=9), nullable=True),
        sa.Column("workflow_status", workflow_status, server_default="submitted", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["department_code"], ["departments.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("vehicle_number"),
    )
    op.create_index("ix_transportations_vehicle_number", "transportations", ["vehicle_number"])
    op.create_index("ix_transportations_department_code", "transportations", ["department_code"])

    op.execute(
        "INSERT INTO warehouse_storages "
        "(code, name, storage_type, plant_code, workflow_status) "
        "SELECT 'GEN-' || code, name || ' General Storage', 'general', code, 'submitted' "
        "FROM plants ON CONFLICT (code) DO NOTHING"
    )
    op.add_column("storage_locations", sa.Column("storage_code", sa.String(length=15), nullable=True))
    op.execute("UPDATE storage_locations SET storage_code = 'GEN-' || plant_code")
    op.alter_column("storage_locations", "storage_code", nullable=False)
    op.create_foreign_key(
        "fk_storage_locations_storage_code",
        "storage_locations",
        "warehouse_storages",
        ["storage_code"],
        ["code"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_storage_locations_storage_code", "storage_locations", ["storage_code"])

    op.add_column(
        "purchase_orders",
        sa.Column("fulfillment_status", fulfillment_status, server_default="open", nullable=False),
    )
    op.create_index("ix_purchase_orders_fulfillment_status", "purchase_orders", ["fulfillment_status"])
    op.add_column(
        "purchase_order_items",
        sa.Column("received_quantity", sa.Numeric(14, 3), server_default="0", nullable=False),
    )

    op.execute("ALTER TABLE sales_orders ALTER COLUMN order_type TYPE VARCHAR(30) USING order_type::text")
    op.execute(
        "UPDATE sales_orders SET order_type = CASE "
        "WHEN order_type = 'regular' THEN 'mass_pro' "
        "WHEN order_type IN ('sample', 'replacement') THEN 'job_order' "
        "ELSE order_type END"
    )
    op.execute("DROP TYPE sales_order_type_enum")
    op.execute("CREATE TYPE sales_order_type_enum AS ENUM ('mass_pro', 'job_order', 'trial')")
    op.execute(
        "ALTER TABLE sales_orders ALTER COLUMN order_type TYPE sales_order_type_enum "
        "USING order_type::sales_order_type_enum"
    )
    op.add_column(
        "sales_orders",
        sa.Column("fulfillment_status", fulfillment_status, server_default="open", nullable=False),
    )
    op.create_index("ix_sales_orders_fulfillment_status", "sales_orders", ["fulfillment_status"])
    op.add_column(
        "sales_order_items",
        sa.Column("material_received_quantity", sa.Numeric(14, 3), server_default="0", nullable=False),
    )
    op.add_column(
        "sales_order_items",
        sa.Column("delivered_quantity", sa.Numeric(14, 3), server_default="0", nullable=False),
    )
    op.add_column("sales_order_items", sa.Column("outstanding_note", sa.Text(), server_default="", nullable=False))

    op.drop_constraint("uq_product_lot", "product_lots", type_="unique")
    op.add_column("product_lots", sa.Column("unit", sa.String(length=10), server_default="gram", nullable=False))
    op.create_unique_constraint(
        "uq_product_lot_location_unit",
        "product_lots",
        ["product_code", "lot_number", "storage_location_code", "unit"],
    )
    op.drop_constraint("receivings_lot_id_key", "receivings", type_="unique")
    op.add_column("receivings", sa.Column("source_type", source_type, nullable=True))
    op.add_column("receivings", sa.Column("source_code", sa.String(length=15), nullable=True))
    op.add_column("receivings", sa.Column("purchase_order_item_id", sa.Integer(), nullable=True))
    op.add_column("receivings", sa.Column("sales_order_item_id", sa.Integer(), nullable=True))
    op.add_column("receivings", sa.Column("transportation_code", sa.String(length=15), nullable=True))
    op.create_foreign_key(
        "fk_receivings_source_code", "receivings", "corporations", ["source_code"], ["code"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "fk_receivings_purchase_order_item",
        "receivings",
        "purchase_order_items",
        ["purchase_order_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_receivings_sales_order_item",
        "receivings",
        "sales_order_items",
        ["sales_order_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_receivings_transportation",
        "receivings",
        "transportations",
        ["transportation_code"],
        ["code"],
        ondelete="RESTRICT",
    )
    for column in (
        "source_type",
        "source_code",
        "purchase_order_item_id",
        "sales_order_item_id",
        "transportation_code",
    ):
        op.create_index(op.f(f"ix_receivings_{column}"), "receivings", [column])
    op.add_column("inventory_movements", sa.Column("unit", sa.String(length=10), server_default="gram", nullable=False))


def downgrade() -> None:
    op.drop_column("inventory_movements", "unit")
    for column in (
        "transportation_code",
        "sales_order_item_id",
        "purchase_order_item_id",
        "source_code",
        "source_type",
    ):
        op.drop_index(op.f(f"ix_receivings_{column}"), table_name="receivings")
    op.drop_constraint("fk_receivings_transportation", "receivings", type_="foreignkey")
    op.drop_constraint("fk_receivings_sales_order_item", "receivings", type_="foreignkey")
    op.drop_constraint("fk_receivings_purchase_order_item", "receivings", type_="foreignkey")
    op.drop_constraint("fk_receivings_source_code", "receivings", type_="foreignkey")
    for column in (
        "transportation_code",
        "sales_order_item_id",
        "purchase_order_item_id",
        "source_code",
        "source_type",
    ):
        op.drop_column("receivings", column)
    op.create_unique_constraint("receivings_lot_id_key", "receivings", ["lot_id"])
    op.drop_constraint("uq_product_lot_location_unit", "product_lots", type_="unique")
    op.drop_column("product_lots", "unit")
    op.create_unique_constraint("uq_product_lot", "product_lots", ["product_code", "lot_number"])
    for column in ("outstanding_note", "delivered_quantity", "material_received_quantity"):
        op.drop_column("sales_order_items", column)
    op.drop_index("ix_sales_orders_fulfillment_status", table_name="sales_orders")
    op.drop_column("sales_orders", "fulfillment_status")
    op.execute("ALTER TABLE sales_orders ALTER COLUMN order_type TYPE VARCHAR(30) USING order_type::text")
    op.execute("DROP TYPE sales_order_type_enum")
    op.execute("CREATE TYPE sales_order_type_enum AS ENUM ('regular', 'sample', 'trial', 'replacement')")
    op.execute("UPDATE sales_orders SET order_type = 'regular' WHERE order_type = 'mass_pro'")
    op.execute("UPDATE sales_orders SET order_type = 'replacement' WHERE order_type = 'job_order'")
    op.execute(
        "ALTER TABLE sales_orders ALTER COLUMN order_type TYPE sales_order_type_enum "
        "USING order_type::sales_order_type_enum"
    )
    op.drop_column("purchase_order_items", "received_quantity")
    op.drop_index("ix_purchase_orders_fulfillment_status", table_name="purchase_orders")
    op.drop_column("purchase_orders", "fulfillment_status")
    op.drop_index("ix_storage_locations_storage_code", table_name="storage_locations")
    op.drop_constraint("fk_storage_locations_storage_code", "storage_locations", type_="foreignkey")
    op.drop_column("storage_locations", "storage_code")
    op.drop_table("transportations")
    for column in ("department_code", "plant_code", "storage_type", "name"):
        op.drop_index(op.f(f"ix_warehouse_storages_{column}"), table_name="warehouse_storages")
    op.drop_table("warehouse_storages")
    op.drop_table("department_pics")
    sa.Enum(name="receiving_source_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="storage_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="fulfillment_status_enum").drop(op.get_bind(), checkfirst=True)
