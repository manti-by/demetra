"""add_sessions_run_attempts_column

Revision ID: 713abfedbf2e
Revises: 5af659d214ed
Create Date: 2026-06-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "713abfedbf2e"
down_revision: str | Sequence[str] | None = "5af659d214ed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "sessions",
        sa.Column("run_attempts", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sessions", "run_attempts")
