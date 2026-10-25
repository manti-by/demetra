"""add_session_history_message_column

Revision ID: e0f1a2b3c4d5
Revises: f0a1b2c3d4e5
Create Date: 2026-10-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e0f1a2b3c4d5"
down_revision: str | Sequence[str] | None = "f0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the ``message`` column carrying the failure reason on a row."""
    op.add_column("session_history", sa.Column("message", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove the ``message`` column."""
    op.drop_column("session_history", "message")
