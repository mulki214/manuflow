"""add independent QR labels

Revision ID: 0036_qr_labels
Revises: 0035_productivity_target_outcome
"""
from alembic import op
import sqlalchemy as sa

revision = "0036_qr_labels"
down_revision = "0035_productivity_target_outcome"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("qr_labels", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("label_name", sa.String(150), nullable=False), sa.Column("template", sa.Text(), nullable=False), sa.Column("resolved_text", sa.Text(), nullable=False), sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_by_name", sa.String(201), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_qr_labels_label_name", "qr_labels", ["label_name"])
    op.create_index("ix_qr_labels_resolved_text", "qr_labels", ["resolved_text"])
    op.create_index("ix_qr_labels_created_by", "qr_labels", ["created_by"])

def downgrade() -> None:
    op.drop_table("qr_labels")
