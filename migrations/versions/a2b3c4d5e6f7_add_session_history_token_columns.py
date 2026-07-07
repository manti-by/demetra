"""add session_history token columns

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-30 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("session_history", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("session_history", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column("session_history", sa.Column("reasoning_tokens", sa.Integer(), nullable=True))
    op.add_column("session_history", sa.Column("cache_read_tokens", sa.Integer(), nullable=True))
    op.add_column("session_history", sa.Column("cache_write_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("session_history", "cache_write_tokens")
    op.drop_column("session_history", "cache_read_tokens")
    op.drop_column("session_history", "reasoning_tokens")
    op.drop_column("session_history", "output_tokens")
    op.drop_column("session_history", "input_tokens")
