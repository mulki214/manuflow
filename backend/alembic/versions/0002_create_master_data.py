"""Create master data tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "code_sequences",
        sa.Column("entity", sa.String(length=30), nullable=False),
        sa.Column("prefix", sa.String(length=12), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("entity", "prefix"),
    )
    op.create_table(
        "corporations",
        sa.Column("code", sa.String(length=15), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("phone_number", sa.String(length=32), nullable=False),
        sa.Column("contact_person_name", sa.String(length=150), nullable=False),
        sa.Column("contact_person_phone", sa.String(length=32), nullable=False),
        sa.Column("npwp", sa.String(length=32), nullable=False),
        sa.Column("is_customer", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_supplier", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index(op.f("ix_corporations_name"), "corporations", ["name"], unique=False)
    op.create_index(op.f("ix_corporations_npwp"), "corporations", ["npwp"], unique=True)
    op.create_table(
        "plants",
        sa.Column("code", sa.String(length=5), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("full_address", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index(op.f("ix_plants_name"), "plants", ["name"], unique=False)
    op.create_table(
        "products",
        sa.Column("code", sa.String(length=15), nullable=False),
        sa.Column("customer_code", sa.String(length=15), nullable=False),
        sa.Column("part_name", sa.String(length=200), nullable=False),
        sa.Column("part_no", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("gross_weight", sa.Float(), nullable=False),
        sa.Column("nett_weight", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["customer_code"], ["corporations.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index(op.f("ix_products_customer_code"), "products", ["customer_code"], unique=False)
    op.create_index(op.f("ix_products_part_name"), "products", ["part_name"], unique=False)
    op.create_index(op.f("ix_products_part_no"), "products", ["part_no"], unique=False)
    op.create_table(
        "machines",
        sa.Column("code", sa.String(length=15), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("specification", sa.Text(), nullable=False),
        sa.Column("machine_type", sa.String(length=100), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("country_of_origin", sa.String(length=100), nullable=False),
        sa.Column("plant_code", sa.String(length=5), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["plant_code"], ["plants.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index(op.f("ix_machines_machine_type"), "machines", ["machine_type"], unique=False)
    op.create_index(op.f("ix_machines_name"), "machines", ["name"], unique=False)
    op.create_index(op.f("ix_machines_plant_code"), "machines", ["plant_code"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_machines_plant_code"), table_name="machines")
    op.drop_index(op.f("ix_machines_name"), table_name="machines")
    op.drop_index(op.f("ix_machines_machine_type"), table_name="machines")
    op.drop_table("machines")
    op.drop_index(op.f("ix_products_part_no"), table_name="products")
    op.drop_index(op.f("ix_products_part_name"), table_name="products")
    op.drop_index(op.f("ix_products_customer_code"), table_name="products")
    op.drop_table("products")
    op.drop_index(op.f("ix_plants_name"), table_name="plants")
    op.drop_table("plants")
    op.drop_index(op.f("ix_corporations_npwp"), table_name="corporations")
    op.drop_index(op.f("ix_corporations_name"), table_name="corporations")
    op.drop_table("corporations")
    op.drop_table("code_sequences")
