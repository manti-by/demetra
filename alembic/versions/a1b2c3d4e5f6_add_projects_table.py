"""Add projects table

Revision ID: a1b2c3d4e5f6
Revises: 2bf40ac4f737
Create Date: 2026-03-30 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "2bf40ac4f737"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "projects",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("linear_project_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("repository_url", sa.String(), nullable=False),
        sa.Column("local_path", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_projects_user_id", "projects")
    op.drop_table("projects")
