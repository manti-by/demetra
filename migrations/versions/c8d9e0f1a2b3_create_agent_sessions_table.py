"""create_agent_sessions_table

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-10-16 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d9e0f1a2b3"
down_revision: str | Sequence[str] | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("step", sa.String(), nullable=False),
        sa.Column("agent", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("fork_of", sa.String(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("cursor_input", sa.Integer(), nullable=True),
        sa.Column("cursor_output", sa.Integer(), nullable=True),
        sa.Column("cursor_reasoning", sa.Integer(), nullable=True),
        sa.Column("cursor_cache_read", sa.Integer(), nullable=True),
        sa.Column("cursor_cache_write", sa.Integer(), nullable=True),
        sa.Column("cursor_cost", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "session_id", name="uq_agent_sessions_task_session"),
    )
    op.create_index("ix_agent_sessions_task_id", "agent_sessions", ["task_id"])
    op.create_index(
        "uq_agent_sessions_primary",
        "agent_sessions",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_agent_sessions_primary", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_task_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")
