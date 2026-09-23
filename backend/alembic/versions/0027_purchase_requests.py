"""add purchase requests

Revision ID: 0027
Revises: 0026
"""
import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("daily_purchase_request_sequences", sa.Column("sequence_date", sa.Date(), primary_key=True), sa.Column("last_value", sa.Integer(), nullable=False))
    op.execute("CREATE TYPE purchase_request_status_enum AS ENUM ('waiting_review', 'approved', 'rejected')")
    op.create_table("purchase_requests", sa.Column("request_number", sa.String(20), primary_key=True), sa.Column("request_date", sa.Date(), nullable=False), sa.Column("department_code", sa.String(15), sa.ForeignKey("departments.code", ondelete="SET NULL")), sa.Column("notes", sa.Text(), nullable=False, server_default=""), sa.Column("status", sa.Enum(name="purchase_request_status_enum", create_type=False), nullable=False, server_default="waiting_review"), sa.Column("created_by", sa.String(9), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("reviewed_by", sa.String(9), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("reviewed_at", sa.DateTime(timezone=True)), sa.Column("rejection_reason", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")))
    op.create_index("ix_purchase_requests_status", "purchase_requests", ["status"]); op.create_index("ix_purchase_requests_created_by", "purchase_requests", ["created_by"])
    op.create_table("purchase_request_items", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("request_number", sa.String(20), sa.ForeignKey("purchase_requests.request_number", ondelete="CASCADE"), nullable=False), sa.Column("line_number", sa.Integer(), nullable=False), sa.Column("product_code", sa.String(30), sa.ForeignKey("products.code", ondelete="RESTRICT"), nullable=False), sa.Column("part_name", sa.String(200), nullable=False), sa.Column("part_no", sa.String(100), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("quantity", sa.Numeric(14,3), nullable=False), sa.Column("unit", sa.String(10), nullable=False), sa.Column("remark", sa.Text(), nullable=False, server_default=""), sa.UniqueConstraint("request_number", "line_number", name="uq_purchase_request_item_line"))


def downgrade() -> None:
    op.drop_table("purchase_request_items"); op.drop_table("purchase_requests"); op.execute("DROP TYPE purchase_request_status_enum"); op.drop_table("daily_purchase_request_sequences")
