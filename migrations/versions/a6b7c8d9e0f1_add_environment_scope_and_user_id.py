"""add_environment_scope_and_user_id

Revision ID: a6b7c8d9e0f1
Revises: a4b5c6d7e8f9
Create Date: 2026-08-10 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a6b7c8d9e0f1"
down_revision: str | Sequence[str] | None = "a4b5c6d7e8f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("project_environment", sa.Column("scope", sa.String(), nullable=False, server_default="project"))
    op.add_column("project_environment", sa.Column("user_id", sa.String(), nullable=True))
    op.create_foreign_key("fk_environment_user_id", "project_environment", "users", ["user_id"], ["id"])

    # Make project_id nullable so user-scoped rows can store no project link.
    op.alter_column("project_environment", "project_id", existing_type=sa.String(), nullable=True)

    # Replace the full unique constraint with partial unique indexes so user
    # rows (project_id IS NULL) never collide with project rows.
    op.drop_constraint("project_environment_project_id_key", "project_environment", type_="unique")
    op.create_index(
        "uq_environment_project_key",
        "project_environment",
        ["project_id", "key"],
        unique=True,
        postgresql_where=sa.text("project_id IS NOT NULL"),
    )
    op.create_index(
        "uq_environment_user_key",
        "project_environment",
        ["user_id", "key"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )

    op.create_check_constraint("ck_environment_scope", "project_environment", "scope IN ('project', 'user')")
    op.create_check_constraint(
        "ck_environment_owner",
        "project_environment",
        "(scope = 'project' AND project_id IS NOT NULL AND user_id IS NULL) "
        "OR (scope = 'user' AND user_id IS NOT NULL AND project_id IS NULL)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_environment_owner", "project_environment", type_="check")
    op.drop_constraint("ck_environment_scope", "project_environment", type_="check")
    op.drop_index("uq_environment_user_key", table_name="project_environment")
    op.drop_index("uq_environment_project_key", table_name="project_environment")
    op.create_unique_constraint("project_environment_project_id_key", "project_environment", ["project_id", "key"])
    op.alter_column("project_environment", "project_id", existing_type=sa.String(), nullable=False)
    op.drop_constraint("fk_environment_user_id", "project_environment", type_="foreignkey")
    op.drop_column("project_environment", "user_id")
    op.drop_column("project_environment", "scope")
