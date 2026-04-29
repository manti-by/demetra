"""Add task_title column to task_status table

Revision ID: d4e5f6a7890
Revises: b2c3d4e5f678
Create Date: 2026-04-29

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "d4e5f6a7890"
down_revision: str = "b2c3d4e5f678"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add task_title column to task_status table."""
    op.add_column("task_status", sa.Column("task_title", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove task_title column from task_status table."""
    op.drop_column("task_status", "task_title")
