"""Lock repository project fields

Revision ID: 556019e457d2
Revises: 7e8f0e492d5b
Create Date: 2026-04-01 17:48:22.685375

"""

from alembic import op

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "556019e457d2"
down_revision: str | Sequence[str] | None = "7e8f0e492d5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("projects", "repository_name", nullable=False)
    op.alter_column("projects", "repository_owner", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("projects", "repository_name", nullable=True)
    op.alter_column("projects", "repository_owner", nullable=True)
