"""Add step field to sessions table

Revision ID: e5f6a7890123
Revises: d4e5f6a78901
Create Date: 2026-05-21 16:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "e5f6a7890123"
down_revision: str | Sequence[str] | None = "d4e5f6a78901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("sessions", sa.Column("step", sa.String(), nullable=False, server_default="initial"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sessions", "step")
