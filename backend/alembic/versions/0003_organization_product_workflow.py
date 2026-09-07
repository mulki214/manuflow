"""Add organization, workflow, product supplier, and gram precision."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    access_level = sa.Enum("staff", "head", "administrator", name="access_level_enum")
    workflow_status = sa.Enum("submitted", name="workflow_status_enum")
    access_level.create(op.get_bind())

    op.create_table(
        "departments",
        sa.Column("code", sa.String(length=15), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("pic_user_id", sa.String(length=9), nullable=True),
        sa.Column("head_user_id", sa.String(length=9), nullable=True),
        sa.Column("owner_department_code", sa.String(length=15), nullable=True),
        sa.Column("created_by", sa.String(length=9), nullable=True),
        sa.Column("workflow_status", workflow_status, server_default="submitted", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["head_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_department_code"], ["departments.code"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pic_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_departments_name"), "departments", ["name"], unique=False)
    op.execute("INSERT INTO departments (code, name) VALUES ('GENERAL', 'General')")

    op.add_column("users", sa.Column("department_code", sa.String(length=15), nullable=True))
    op.add_column("users", sa.Column("access_level", access_level, server_default="staff", nullable=False))
    op.create_foreign_key(
        "fk_users_department_code", "users", "departments", ["department_code"], ["code"], ondelete="RESTRICT"
    )
    op.create_index(op.f("ix_users_department_code"), "users", ["department_code"], unique=False)
    op.execute("UPDATE users SET department_code = 'GENERAL'")
    op.execute("UPDATE users SET access_level = 'administrator' WHERE lower(role) = 'administrator'")

    for table in ("corporations", "plants", "products", "machines"):
        op.add_column(table, sa.Column("department_code", sa.String(length=15), nullable=True))
        op.add_column(table, sa.Column("created_by", sa.String(length=9), nullable=True))
        op.add_column(
            table,
            sa.Column("workflow_status", workflow_status, server_default="submitted", nullable=False),
        )
        op.create_foreign_key(
            f"fk_{table}_department_code",
            table,
            "departments",
            ["department_code"],
            ["code"],
            ondelete="RESTRICT",
        )
        op.create_foreign_key(f"fk_{table}_created_by", table, "users", ["created_by"], ["id"], ondelete="SET NULL")
        op.create_index(op.f(f"ix_{table}_department_code"), table, ["department_code"], unique=False)
        op.execute(f"UPDATE {table} SET department_code = 'GENERAL'")

    op.add_column("products", sa.Column("supplier_code", sa.String(length=15), nullable=True))
    op.execute("UPDATE products SET supplier_code = customer_code")
    op.execute(
        "UPDATE corporations SET is_supplier = true "
        "WHERE code IN (SELECT DISTINCT supplier_code FROM products)"
    )
    op.alter_column("products", "supplier_code", nullable=False)
    op.create_foreign_key(
        "fk_products_supplier_code",
        "products",
        "corporations",
        ["supplier_code"],
        ["code"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_products_supplier_code"), "products", ["supplier_code"], unique=False)
    op.alter_column(
        "products",
        "gross_weight",
        existing_type=sa.Float(),
        type_=sa.Numeric(14, 3),
        existing_nullable=False,
        postgresql_using="gross_weight::numeric(14,3)",
    )
    op.alter_column(
        "products",
        "nett_weight",
        existing_type=sa.Float(),
        type_=sa.Numeric(14, 3),
        existing_nullable=False,
        postgresql_using="nett_weight::numeric(14,3)",
    )


def downgrade() -> None:
    op.alter_column(
        "products",
        "nett_weight",
        existing_type=sa.Numeric(14, 3),
        type_=sa.Float(),
        postgresql_using="nett_weight::float",
    )
    op.alter_column(
        "products",
        "gross_weight",
        existing_type=sa.Numeric(14, 3),
        type_=sa.Float(),
        postgresql_using="gross_weight::float",
    )
    op.drop_index(op.f("ix_products_supplier_code"), table_name="products")
    op.drop_constraint("fk_products_supplier_code", "products", type_="foreignkey")
    op.drop_column("products", "supplier_code")
    for table in ("machines", "products", "plants", "corporations"):
        op.drop_index(op.f(f"ix_{table}_department_code"), table_name=table)
        op.drop_constraint(f"fk_{table}_created_by", table, type_="foreignkey")
        op.drop_constraint(f"fk_{table}_department_code", table, type_="foreignkey")
        op.drop_column(table, "workflow_status")
        op.drop_column(table, "created_by")
        op.drop_column(table, "department_code")
    op.drop_index(op.f("ix_users_department_code"), table_name="users")
    op.drop_constraint("fk_users_department_code", "users", type_="foreignkey")
    op.drop_column("users", "access_level")
    op.drop_column("users", "department_code")
    op.drop_index(op.f("ix_departments_name"), table_name="departments")
    op.drop_table("departments")
    sa.Enum(name="workflow_status_enum").drop(op.get_bind())
    sa.Enum(name="access_level_enum").drop(op.get_bind())
