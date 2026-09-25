"""add standalone sales quotations

Revision ID: 0032
Revises: 0031
"""

from alembic import op
import sqlalchemy as sa


revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_quotation_sequences",
        sa.Column("sequence_date", sa.Date(), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False),
    )
    op.create_table(
        "quotations",
        sa.Column("quotation_number", sa.String(20), primary_key=True),
        sa.Column("quotation_date", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("customer_code", sa.String(15), sa.ForeignKey("corporations.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("customer_address", sa.Text(), nullable=False),
        sa.Column("customer_phone", sa.String(32), nullable=False),
        sa.Column("customer_contact_person", sa.String(150), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("payment_terms", sa.Text(), nullable=False, server_default=""),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IDR"),
        sa.Column("subtotal", sa.Numeric(20, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("tax_label", sa.String(50), nullable=False, server_default="PPN"),
        sa.Column("tax_rate", sa.Numeric(6, 3), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("grand_total", sa.Numeric(20, 2), nullable=False),
        sa.Column("department_code", sa.String(15), sa.ForeignKey("departments.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by", sa.String(9), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_quotations_quotation_date", "quotations", ["quotation_date"])
    op.create_index("ix_quotations_valid_until", "quotations", ["valid_until"])
    op.create_index("ix_quotations_customer_code", "quotations", ["customer_code"])
    op.create_index("ix_quotations_department_code", "quotations", ["department_code"])
    op.create_table(
        "quotation_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("quotation_number", sa.String(20), sa.ForeignKey("quotations.quotation_number", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(15), sa.ForeignKey("products.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("part_name", sa.String(200), nullable=False),
        sa.Column("part_no", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("unit_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("remark", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_quotation_items_quotation_number", "quotation_items", ["quotation_number"])
    op.create_index("ix_quotation_items_product_code", "quotation_items", ["product_code"])


def downgrade() -> None:
    op.drop_table("quotation_items")
    op.drop_table("quotations")
    op.drop_table("daily_quotation_sequences")
