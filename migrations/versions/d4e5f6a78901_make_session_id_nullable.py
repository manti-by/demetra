"""Make session_id nullable in sessions table

Revision ID: d4e5f6a78901
Revises: 556019e457d2
Create Date: 2026-05-21 15:45:00.000000

"""

from alembic import op

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a78901"
down_revision: str | Sequence[str] | None = "collapse_task_status_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("sessions", "session_id", nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("sessions", "session_id", nullable=False)
