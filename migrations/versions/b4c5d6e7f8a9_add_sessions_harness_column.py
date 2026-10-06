"""add_sessions_harness_column

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-09-30 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: str | Sequence[str] | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "sessions",
        sa.Column("harness", sa.String(), nullable=False, server_default="opencode"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sessions", "harness")
