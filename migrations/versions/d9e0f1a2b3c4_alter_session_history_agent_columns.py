"""alter_session_history_agent_columns

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-10-16 12:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9e0f1a2b3c4"
down_revision: str | Sequence[str] | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema and backfill invocation attribution.

    ``session_id`` is relaxed to nullable (research never had one), the new
    ``task_id``/``kind``/``cost``/``agent`` columns are added and
    ``agent_session_id`` is an FK to ``agent_sessions.id`` (Postgres requires
    the FK target to be a unique key, which ``id`` is). The ``kind`` column is
    backfilled to ``'invocation'`` for legacy rows carrying any token count so
    existing per-session totals are preserved; rows without tokens stay
    ``'step'``.
    """
    op.add_column("session_history", sa.Column("task_id", sa.String(), nullable=True))
    op.add_column("session_history", sa.Column("agent_session_id", sa.String(), nullable=True))
    op.add_column(
        "session_history",
        sa.Column("kind", sa.String(), nullable=False, server_default="step"),
    )
    op.add_column("session_history", sa.Column("cost", sa.Float(), nullable=True))
    op.add_column("session_history", sa.Column("agent", sa.String(), nullable=True))
    op.alter_column("session_history", "session_id", existing_type=sa.String(), nullable=True)
    op.create_foreign_key(
        "fk_session_history_agent_session_id",
        "session_history",
        "agent_sessions",
        ["agent_session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_session_history_task_id", "session_history", ["task_id"])

    # Backfill the owning task from the session pointer so history resolves by
    # task_id after the migration.
    op.execute(
        """
        UPDATE session_history h
           SET task_id = s.task_id
          FROM sessions s
         WHERE h.session_id = s.session_id
           AND h.task_id IS NULL
        """
    )

    # Legacy rows that carry any token count are real invocations; the rest are
    # empty step markers.
    op.execute(
        """
        UPDATE session_history
           SET kind = 'invocation'
         WHERE input_tokens IS NOT NULL
            OR output_tokens IS NOT NULL
            OR reasoning_tokens IS NOT NULL
            OR cache_read_tokens IS NOT NULL
            OR cache_write_tokens IS NOT NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_session_history_task_id", table_name="session_history")
    op.drop_constraint("fk_session_history_agent_session_id", "session_history", type_="foreignkey")
    # ``kind='step'`` rows have a NULL ``session_id``; the pre-MNT-251 schema
    # required it, so they cannot survive the downgrade and must be removed
    # before the constraint is restored or the ALTER COLUMN fails.
    op.execute("DELETE FROM session_history WHERE session_id IS NULL")
    op.alter_column("session_history", "session_id", existing_type=sa.String(), nullable=False)
    op.drop_column("session_history", "agent")
    op.drop_column("session_history", "cost")
    op.drop_column("session_history", "kind")
    op.drop_column("session_history", "agent_session_id")
    op.drop_column("session_history", "task_id")
