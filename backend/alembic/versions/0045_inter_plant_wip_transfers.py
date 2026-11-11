"""Add audited inter-plant WIP transfers with dispatch and receipt states.

Revision ID: 0045_inter_plant_wip_transfers
Revises: 0044_order_revisions
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0045_inter_plant_wip_transfers"
down_revision = "0044_order_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    status_enum = postgresql.ENUM(
        "in_transit",
        "received",
        name="inter_plant_wip_transfer_status_enum",
    )
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "inter_plant_wip_transfers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("transfer_date", sa.Date(), nullable=False),
        sa.Column("source_job_id", sa.Integer(), nullable=False),
        sa.Column("received_job_id", sa.Integer(), nullable=True),
        sa.Column("product_code", sa.String(length=15), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("lot_number", sa.String(length=100), nullable=False),
        sa.Column("lot_segment_code", sa.String(length=40), nullable=False),
        sa.Column("unit", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=20, scale=3), nullable=False),
        sa.Column("source_plant_code", sa.String(length=5), nullable=False),
        sa.Column("source_plant_name", sa.String(length=150), nullable=False),
        sa.Column("source_process_code", sa.String(length=20), nullable=False),
        sa.Column("source_process_name", sa.String(length=150), nullable=False),
        sa.Column("destination_plant_code", sa.String(length=5), nullable=False),
        sa.Column("destination_plant_name", sa.String(length=150), nullable=False),
        sa.Column("destination_process_code", sa.String(length=20), nullable=False),
        sa.Column("destination_process_name", sa.String(length=150), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("dispatched_by", sa.String(length=9), nullable=False),
        sa.Column("dispatched_by_name", sa.String(length=201), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("received_by", sa.String(length=9), nullable=True),
        sa.Column("received_by_name", sa.String(length=201), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_job_id"], ["wip_lot_jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["received_job_id"], ["wip_lot_jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_code"], ["products.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_plant_code"], ["plants.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_process_code"], ["wip_processes.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["destination_plant_code"], ["plants.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["destination_process_code"], ["wip_processes.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["dispatched_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["received_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("received_job_id", name="uq_interplant_received_job"),
    )
    op.create_index("ix_inter_plant_wip_transfers_transfer_date", "inter_plant_wip_transfers", ["transfer_date"])
    op.create_index("ix_inter_plant_wip_transfers_source_job_id", "inter_plant_wip_transfers", ["source_job_id"])
    op.create_index("ix_inter_plant_wip_transfers_product_code", "inter_plant_wip_transfers", ["product_code"])
    op.create_index("ix_inter_plant_wip_transfers_lot_number", "inter_plant_wip_transfers", ["lot_number"])
    op.create_index(
        "ix_inter_plant_wip_transfers_source_plant_code", "inter_plant_wip_transfers", ["source_plant_code"]
    )
    op.create_index(
        "ix_inter_plant_wip_transfers_destination_plant_code",
        "inter_plant_wip_transfers",
        ["destination_plant_code"],
    )
    op.create_index("ix_inter_plant_wip_transfers_status", "inter_plant_wip_transfers", ["status"])


def downgrade() -> None:
    op.drop_index("ix_inter_plant_wip_transfers_status", table_name="inter_plant_wip_transfers")
    op.drop_index("ix_inter_plant_wip_transfers_destination_plant_code", table_name="inter_plant_wip_transfers")
    op.drop_index("ix_inter_plant_wip_transfers_source_plant_code", table_name="inter_plant_wip_transfers")
    op.drop_index("ix_inter_plant_wip_transfers_lot_number", table_name="inter_plant_wip_transfers")
    op.drop_index("ix_inter_plant_wip_transfers_product_code", table_name="inter_plant_wip_transfers")
    op.drop_index("ix_inter_plant_wip_transfers_source_job_id", table_name="inter_plant_wip_transfers")
    op.drop_index("ix_inter_plant_wip_transfers_transfer_date", table_name="inter_plant_wip_transfers")
    op.drop_table("inter_plant_wip_transfers")
    postgresql.ENUM(name="inter_plant_wip_transfer_status_enum").drop(op.get_bind(), checkfirst=True)
