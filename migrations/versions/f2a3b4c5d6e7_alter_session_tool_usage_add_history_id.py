"""alter_session_tool_usage_add_history_id

Revision ID: f2a3b4c5d6e7
Revises: e0f1a2b3c4d5
Create Date: 2026-10-25 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "e0f1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("session_tool_usage", sa.Column("history_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_session_tool_usage_history_id",
        "session_tool_usage",
        "session_history",
        ["history_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        """
        UPDATE session_tool_usage AS stu
           SET history_id = (
               SELECT sh.id
                 FROM session_history AS sh
                WHERE sh.agent_session_id = stu.agent_session_id
                  AND sh.step = stu.step
                  AND sh.kind = 'invocation'
                ORDER BY sh.created_at, sh.id
                LIMIT 1
           )
         WHERE stu.history_id IS NULL
        """
    )
    op.drop_constraint("uq_session_tool_usage_row", "session_tool_usage", type_="unique")
    op.create_unique_constraint("uq_session_tool_usage_history", "session_tool_usage", ["history_id", "tool_name"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_session_tool_usage_history", "session_tool_usage", type_="unique")
    op.execute(
        """
        CREATE TABLE session_tool_usage_merged AS
        SELECT min(id) AS id,
               min(task_id) AS task_id,
               agent_session_id,
               step,
               tool_name,
               sum(calls) AS calls,
               sum(succeeded) AS succeeded,
               sum(failed) AS failed,
               sum(duration_ms) AS duration_ms,
               min(created_at) AS created_at,
               max(updated_at) AS updated_at
          FROM session_tool_usage
         GROUP BY agent_session_id, step, tool_name
        """
    )
    op.execute("DELETE FROM session_tool_usage")
    op.execute(
        """
        INSERT INTO session_tool_usage
            (id, task_id, agent_session_id, step, tool_name, calls, succeeded, failed, duration_ms, created_at, updated_at)
        SELECT id, task_id, agent_session_id, step, tool_name, calls, succeeded, failed, duration_ms, created_at, updated_at
          FROM session_tool_usage_merged
        """
    )
    op.execute("DROP TABLE session_tool_usage_merged")
    op.drop_constraint("fk_session_tool_usage_history_id", "session_tool_usage", type_="foreignkey")
    op.drop_column("session_tool_usage", "history_id")
    op.create_unique_constraint(
        "uq_session_tool_usage_row", "session_tool_usage", ["agent_session_id", "step", "tool_name"]
    )
