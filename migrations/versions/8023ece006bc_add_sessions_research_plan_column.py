"""add_sessions_research_plan_column

Revision ID: 8023ece006bc
Revises: e7f8a9b0c1d2
Create Date: 2026-09-11 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8023ece006bc"
down_revision: str | Sequence[str] | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "sessions",
        sa.Column("research_plan", sa.Text(), server_default="", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sessions", "research_plan")
