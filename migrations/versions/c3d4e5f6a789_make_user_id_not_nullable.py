"""Make user_id non-nullable in projects table

Revision ID: c3d4e5f6a789
Revises: a1b2c3d4e5f6
Create Date: 2026-03-30

"""

from collections.abc import Sequence

from alembic import op


revision: str = "c3d4e5f6a789"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Make user_id non-nullable and backfill NULL values."""
    op.execute("UPDATE projects SET user_id = '' WHERE user_id IS NULL")
    op.alter_column("projects", "user_id", nullable=False)


def downgrade() -> None:
    """Allow user_id to be nullable again."""
    op.alter_column("projects", "user_id", nullable=True)
