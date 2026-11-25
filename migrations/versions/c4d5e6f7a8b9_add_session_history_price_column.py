"""add_session_history_price_column

Revision ID: c4d5e6f7a8b9
Revises: b0c1d2e3f4a5
Create Date: 2026-11-24 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "b0c1d2e3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the ``price`` column holding the rate snapshot used for a row."""
    op.add_column("session_history", sa.Column("price", JSONB(), nullable=True))


def downgrade() -> None:
    """Remove the ``price`` column."""
    op.drop_column("session_history", "price")
