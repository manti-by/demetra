"""Add state column to projects table

Revision ID: b2c3d4e5f678
Revises: a1b2c3d4e5f6
Create Date: 2026-03-30

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "b2c3d4e5f678"
down_revision: str = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add state column to projects table."""
    op.add_column("projects", sa.Column("state", sa.String(), server_default="provisioning", nullable=False))


def downgrade() -> None:
    """Remove state column from projects table."""
    op.drop_column("projects", "state")
