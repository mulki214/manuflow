"""link POs to Sales Orders and track subcontract dispatches

Revision ID: 0037_so_subcontracting
Revises: 0036_qr_labels
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0037_so_subcontracting"
down_revision = "0036_qr_labels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the PostgreSQL types explicitly below. Disabling SQLAlchemy's
    # implicit table/column DDL avoids a second CREATE TYPE during migration.
    order_kind = postgresql.ENUM(
        "purchase", "subcontract", name="purchase_order_kind_enum", create_type=False
    )
    dispatch_status = postgresql.ENUM(
        "dispatched",
        "partially_received",
        "received",
        "reversed",
        name="subcontract_dispatch_status_enum",
        create_type=False,
    )
    order_kind.create(op.get_bind(), checkfirst=True)
    dispatch_status.create(op.get_bind(), checkfirst=True)
    op.execute("ALTER TYPE wip_lot_status_enum ADD VALUE IF NOT EXISTS 'subcontracted'")

    op.add_column("purchase_orders", sa.Column("sales_order_number", sa.String(20), nullable=True))
    op.add_column("purchase_orders", sa.Column("order_kind", order_kind, nullable=False, server_default="purchase"))
    op.create_index("ix_purchase_orders_sales_order_number", "purchase_orders", ["sales_order_number"])
    op.create_foreign_key(
        "fk_purchase_orders_sales_order_number_sales_orders",
        "purchase_orders",
        "sales_orders",
        ["sales_order_number"],
        ["sales_order_number"],
        ondelete="RESTRICT",
    )
    op.add_column("purchase_order_items", sa.Column("sales_order_item_id", sa.Integer(), nullable=True))
    op.add_column("purchase_order_items", sa.Column("process_from_code", sa.String(20), nullable=True))
    op.add_column("purchase_order_items", sa.Column("process_to_code", sa.String(20), nullable=True))
    op.create_index("ix_purchase_order_items_sales_order_item_id", "purchase_order_items", ["sales_order_item_id"])
    op.create_foreign_key(
        "fk_purchase_order_items_sales_order_item_id_sales_order_items",
        "purchase_order_items",
        "sales_order_items",
        ["sales_order_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_purchase_order_items_process_from_code_wip_processes",
        "purchase_order_items",
        "wip_processes",
        ["process_from_code"],
        ["code"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_purchase_order_items_process_to_code_wip_processes",
        "purchase_order_items",
        "wip_processes",
        ["process_to_code"],
        ["code"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "subcontract_dispatches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dispatch_number", sa.String(24), nullable=False, unique=True),
        sa.Column("purchase_order_item_id", sa.Integer(), nullable=False),
        sa.Column("source_lot_id", sa.Integer(), nullable=True),
        sa.Column("source_wip_job_id", sa.Integer(), nullable=True),
        sa.Column("product_code", sa.String(15), nullable=False),
        sa.Column("lot_number", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("expected_output_quantity", sa.Numeric(20, 3), nullable=False),
        sa.Column("source_process_code", sa.String(20), nullable=True),
        sa.Column("process_to_code", sa.String(20), nullable=False),
        sa.Column("subcontractor_code", sa.String(15), nullable=False),
        sa.Column("status", dispatch_status, nullable=False, server_default="dispatched"),
        sa.Column("returned_quantity", sa.Numeric(20, 3), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("dispatched_by", sa.String(9), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["purchase_order_item_id"], ["purchase_order_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_lot_id"], ["product_lots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_wip_job_id"], ["wip_lot_jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_code"], ["products.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_process_code"], ["wip_processes.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["process_to_code"], ["wip_processes.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subcontractor_code"], ["corporations.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["dispatched_by"], ["users.id"], ondelete="RESTRICT"),
    )
    for column in (
        "dispatch_number",
        "purchase_order_item_id",
        "source_lot_id",
        "source_wip_job_id",
        "subcontractor_code",
        "status",
    ):
        op.create_index(f"ix_subcontract_dispatches_{column}", "subcontract_dispatches", [column])
    op.add_column("receivings", sa.Column("subcontract_dispatch_id", sa.Integer(), nullable=True))
    op.create_index("ix_receivings_subcontract_dispatch_id", "receivings", ["subcontract_dispatch_id"])
    op.create_foreign_key(
        "fk_receivings_subcontract_dispatch_id_subcontract_dispatches",
        "receivings",
        "subcontract_dispatches",
        ["subcontract_dispatch_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_receivings_subcontract_dispatch_id_subcontract_dispatches", "receivings", type_="foreignkey")
    op.drop_index("ix_receivings_subcontract_dispatch_id", table_name="receivings")
    op.drop_column("receivings", "subcontract_dispatch_id")
    op.drop_table("subcontract_dispatches")
    op.drop_constraint(
        "fk_purchase_order_items_process_to_code_wip_processes", "purchase_order_items", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_purchase_order_items_process_from_code_wip_processes", "purchase_order_items", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_purchase_order_items_sales_order_item_id_sales_order_items", "purchase_order_items", type_="foreignkey"
    )
    op.drop_index("ix_purchase_order_items_sales_order_item_id", table_name="purchase_order_items")
    op.drop_column("purchase_order_items", "process_to_code")
    op.drop_column("purchase_order_items", "process_from_code")
    op.drop_column("purchase_order_items", "sales_order_item_id")
    op.drop_constraint("fk_purchase_orders_sales_order_number_sales_orders", "purchase_orders", type_="foreignkey")
    op.drop_index("ix_purchase_orders_sales_order_number", table_name="purchase_orders")
    op.drop_column("purchase_orders", "order_kind")
    op.drop_column("purchase_orders", "sales_order_number")
    sa.Enum(name="subcontract_dispatch_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="purchase_order_kind_enum").drop(op.get_bind(), checkfirst=True)
