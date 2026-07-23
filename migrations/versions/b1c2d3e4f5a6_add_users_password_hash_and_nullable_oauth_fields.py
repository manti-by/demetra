"""add_users_password_hash_and_nullable_oauth_fields

Revision ID: b1c2d3e4f5a6
Revises: c23d0030e347
Create Date: 2026-07-24 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str | Sequence[str] | None = "c23d0030e347"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))
    op.alter_column("users", "github_id", existing_type=sa.String(), nullable=True)
    op.alter_column("users", "github_username", existing_type=sa.String(), nullable=True)
    op.alter_column("users", "email", existing_type=sa.String(), nullable=False)
    op.drop_constraint("users_github_id_key", "users", type_="unique")
    op.create_index(
        "uq_users_github_id", "users", ["github_id"], unique=True, postgresql_where=sa.text("github_id IS NOT NULL")
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_check_constraint("ck_users_has_auth", "users", "password_hash IS NOT NULL OR github_id IS NOT NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_users_has_auth", "users", type_="check")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("uq_users_github_id", table_name="users")
    op.create_unique_constraint("users_github_id_key", "users", ["github_id"])
    op.alter_column("users", "email", existing_type=sa.String(), nullable=True)
    op.alter_column("users", "github_username", existing_type=sa.String(), nullable=False)
    op.alter_column("users", "github_id", existing_type=sa.String(), nullable=False)
    op.drop_column("users", "password_hash")
