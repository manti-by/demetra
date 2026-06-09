"""add_sessions_pr_link_column

Revision ID: c3c1ac1a5769
Revises: 713abfedbf2e
Create Date: 2026-06-09 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3c1ac1a5769"
down_revision: str | Sequence[str] | None = "713abfedbf2e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "sessions",
        sa.Column("pr_link", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sessions", "pr_link")
