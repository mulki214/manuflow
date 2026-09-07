"""Create users and daily sequence tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    gender = sa.Enum("male", "female", name="gender_enum")
    op.create_table(
        "daily_user_sequences",
        sa.Column("sequence_date", sa.Date(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("sequence_date"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=9), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("gender", gender, nullable=False),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("ktp_number", sa.String(length=16), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_ktp_number"), "users", ["ktp_number"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_ktp_number"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_table("daily_user_sequences")
    sa.Enum(name="gender_enum").drop(op.get_bind())
