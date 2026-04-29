"""Add name column to sessions table

Revision ID: 4a8b9c0d1e2f
Revises: qbof4yrxlne2
Create Date: 2026-05-22

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "4a8b9c0d1e2f"
down_revision: str | Sequence[str] | None = "qbof4yrxlne2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add name column to sessions table."""
    op.add_column("sessions", sa.Column("name", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove name column from sessions table."""
    op.drop_column("sessions", "name")
