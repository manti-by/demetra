"""add_session_history_context_model_columns

Revision ID: c23d0030e347
Revises: b3c4d5e6f7a8
Create Date: 2026-07-23 15:44:15.627127

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c23d0030e347"
down_revision: str | Sequence[str] | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("session_history", sa.Column("context_tokens", sa.Integer(), nullable=True))
    op.add_column("session_history", sa.Column("model", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("session_history", "model")
    op.drop_column("session_history", "context_tokens")
