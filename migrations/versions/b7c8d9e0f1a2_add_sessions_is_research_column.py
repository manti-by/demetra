"""add_sessions_is_research_column

Revision ID: b7c8d9e0f1a2
Revises: a3b4c5d6e7f8
Create Date: 2026-10-12 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "sessions",
        sa.Column("is_research", sa.Boolean(), nullable=False, server_default="false"),
    )

    # Backfill sessions stuck in the research step, which only the research
    # workflow ever writes. The ``awaiting_input`` step is deliberately not
    # used as a marker: the plan workflow writes it too.
    op.execute("UPDATE sessions SET is_research = true WHERE step = 'research'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sessions", "is_research")
