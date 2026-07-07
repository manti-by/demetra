"""add_session_history_table

Revision ID: f1a2b3c4d5e6
Revises: d9e8f7c0b1a2
Create Date: 2026-06-30 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "d9e8f7c0b1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "session_history",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("step", sa.String(), nullable=False),
        sa.Column(
            "length",
            sa.Integer(),
            nullable=True,
            comment="Total token count at this point in the session",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_session_history_session_id",
        "session_history",
        ["session_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_session_history_session_id", table_name="session_history")
    op.drop_table("session_history")
