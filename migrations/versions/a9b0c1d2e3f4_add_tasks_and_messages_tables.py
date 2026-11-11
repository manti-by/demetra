"""add_tasks_and_messages_tables

Introduce the generic task entity and the unified message history.

The ``sessions`` table keeps the workflow state, a new ``tasks`` table holds
the identity of a unit of work (a Linear issue or a chat session), and a new
``messages`` table holds the conversation history of both sources. The
``chat_messages`` table is folded into ``messages`` and the duplicated,
foreign-key-less ``session_task_id`` column is dropped.

Revision ID: a9b0c1d2e3f4
Revises: e8f9a0b1c2d3
Create Date: 2026-11-11 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9b0c1d2e3f4"
down_revision: str | Sequence[str] | None = "e8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CHAT_TASK_BACKFILL = """
INSERT INTO tasks (id, kind, identifier, title, description, priority, state, url, tags, project_id, user_id, created_at, updated_at)
SELECT
    c.session_task_id,
    'chat',
    c.session_task_id,
    c.title,
    c.description,
    0,
    s.step,
    NULL,
    c.tags,
    CASE WHEN EXISTS (SELECT 1 FROM projects p WHERE p.id = c.project_id) THEN c.project_id ELSE NULL END,
    CASE WHEN EXISTS (SELECT 1 FROM users u WHERE u.id = c.user_id) THEN c.user_id ELSE NULL END,
    c.created_at,
    c.updated_at
FROM chats c
LEFT JOIN sessions s ON s.task_id = c.session_task_id
ON CONFLICT (id) DO NOTHING
"""

LINEAR_TASK_BACKFILL = """
INSERT INTO tasks (id, kind, identifier, title, description, priority, state, url, tags, project_id, user_id, created_at, updated_at)
SELECT
    s.task_id,
    'linear',
    CASE
        WHEN s.name IS NULL THEN s.task_id
        WHEN position(':' in s.name) > 0 THEN split_part(s.name, ':', 1)
        ELSE s.name
    END,
    CASE
        WHEN s.name IS NULL THEN ''
        WHEN position(':' in s.name) > 0 THEN trim(substr(s.name, position(':' in s.name) + 1))
        ELSE s.name
    END,
    '',
    0,
    s.step,
    s.linear_link,
    '[]'::jsonb,
    CASE WHEN EXISTS (SELECT 1 FROM projects p WHERE p.id = s.project_id) THEN s.project_id ELSE NULL END,
    CASE WHEN EXISTS (SELECT 1 FROM users u WHERE u.id = s.user_id) THEN s.user_id ELSE NULL END,
    s.created_at,
    s.updated_at
FROM sessions s
WHERE NOT EXISTS (SELECT 1 FROM chats c WHERE c.session_task_id = s.task_id)
ON CONFLICT (id) DO NOTHING
"""

MESSAGE_BACKFILL = """
INSERT INTO messages (id, task_id, parent_id, source, external_id, author_id, author_name, is_system, kind, body, created_at)
SELECT
    cm.id,
    cm.session_task_id,
    NULL,
    'chat',
    NULL,
    cm.author_id,
    NULL,
    cm.is_system,
    cm.kind,
    cm.body,
    cm.created_at
FROM chat_messages cm
WHERE EXISTS (SELECT 1 FROM tasks t WHERE t.id = cm.session_task_id)
"""

CHAT_RESTORE = """
UPDATE chats c
SET
    title = COALESCE(t.title, ''),
    description = COALESCE(t.description, ''),
    tags = COALESCE(t.tags, '[]'::jsonb),
    user_id = COALESCE(t.user_id, ''),
    project_id = COALESCE(t.project_id, ''),
    created_at = COALESCE(t.created_at, NOW()),
    updated_at = COALESCE(t.updated_at, NOW())
FROM tasks t
WHERE t.id = c.task_id
"""

CHAT_MESSAGE_RESTORE = """
INSERT INTO chat_messages (id, chat_id, session_task_id, author_id, is_system, kind, body, created_at)
SELECT
    m.id,
    c.id,
    m.task_id,
    m.author_id,
    m.is_system,
    m.kind,
    m.body,
    m.created_at
FROM messages m
JOIN chats c ON c.task_id = m.task_id
WHERE m.source = 'chat'
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("identifier", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("project_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('linear', 'chat')", name="ck_tasks_kind"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_kind", "tasks", ["kind"], unique=False)
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"], unique=False)

    op.create_table(
        "linear_tasks",
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("linear_issue_id", sa.String(), nullable=False),
        sa.Column("linear_identifier", sa.String(), nullable=True),
        sa.Column("linear_state_id", sa.String(), nullable=True),
        sa.Column("linear_state_name", sa.String(), nullable=True),
        sa.Column("linear_project_id", sa.String(), nullable=True),
        sa.Column("branch_name", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id"),
        sa.UniqueConstraint("linear_issue_id", name="uq_linear_tasks_issue_id"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("parent_id", sa.String(), nullable=True),
        sa.Column("source", sa.String(), server_default="chat", nullable=False),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("author_id", sa.String(), nullable=True),
        sa.Column("author_name", sa.String(), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("kind", sa.String(), server_default="message", nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source IN ('chat', 'linear')", name="ck_messages_source"),
        sa.CheckConstraint(
            "kind IN ('message', 'question', 'plan', 'failure', 'research', 'status', 'comment')",
            name="ck_messages_kind",
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_task_id", "messages", ["task_id"], unique=False)
    op.create_index("ix_messages_parent_id", "messages", ["parent_id"], unique=False)
    op.create_index(
        "uq_messages_external_id",
        "messages",
        ["external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    op.execute(CHAT_TASK_BACKFILL)
    op.execute(LINEAR_TASK_BACKFILL)
    op.execute(MESSAGE_BACKFILL)

    op.drop_index("ix_chat_messages_session_task_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_constraint("uq_chats_session_task_id", "chats", type_="unique")
    op.drop_constraint("chats_session_task_id_fkey", "chats", type_="foreignkey")
    op.drop_constraint("chats_project_id_fkey", "chats", type_="foreignkey")
    op.drop_constraint("chats_user_id_fkey", "chats", type_="foreignkey")
    op.drop_index("ix_chats_user_id", table_name="chats")
    op.drop_index("ix_chats_project_id", table_name="chats")
    op.add_column("chats", sa.Column("task_id", sa.String(), nullable=True))
    op.execute("UPDATE chats SET task_id = session_task_id")
    op.alter_column("chats", "task_id", nullable=False)
    op.create_foreign_key("chats_task_id_fkey", "chats", "tasks", ["task_id"], ["id"], ondelete="CASCADE")
    op.create_unique_constraint("uq_chats_task_id", "chats", ["task_id"])
    op.drop_column("chats", "session_task_id")
    op.drop_column("chats", "title")
    op.drop_column("chats", "description")
    op.drop_column("chats", "tags")
    op.drop_column("chats", "user_id")
    op.drop_column("chats", "project_id")
    op.drop_column("chats", "created_at")
    op.drop_column("chats", "updated_at")

    op.create_foreign_key("sessions_task_id_fkey", "sessions", "tasks", ["task_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("sessions_task_id_fkey", "sessions", type_="foreignkey")

    op.add_column("chats", sa.Column("title", sa.String(), nullable=True))
    op.add_column("chats", sa.Column("description", sa.Text(), server_default="", nullable=True))
    op.add_column("chats", sa.Column("tags", postgresql.JSONB(), server_default="[]", nullable=True))
    op.add_column("chats", sa.Column("user_id", sa.String(), nullable=True))
    op.add_column("chats", sa.Column("project_id", sa.String(), nullable=True))
    op.add_column("chats", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("chats", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(CHAT_RESTORE)
    op.alter_column("chats", "title", nullable=False)
    op.alter_column("chats", "description", nullable=False)
    op.alter_column("chats", "tags", nullable=False)
    op.alter_column("chats", "user_id", nullable=False)
    op.alter_column("chats", "project_id", nullable=False)
    op.alter_column("chats", "created_at", nullable=False)
    op.alter_column("chats", "updated_at", nullable=False)

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("session_task_id", sa.String(), nullable=False),
        sa.Column("author_id", sa.String(), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("kind", sa.String(), server_default="message", nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('message', 'question', 'plan', 'failure', 'research', 'status')",
            name="ck_chat_messages_kind",
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_session_task_id", "chat_messages", ["session_task_id"], unique=False)
    op.execute(CHAT_MESSAGE_RESTORE)

    op.add_column("chats", sa.Column("session_task_id", sa.String(), nullable=True))
    op.execute("UPDATE chats SET session_task_id = task_id")
    op.alter_column("chats", "session_task_id", nullable=False)
    op.drop_constraint("uq_chats_task_id", "chats", type_="unique")
    op.drop_constraint("chats_task_id_fkey", "chats", type_="foreignkey")
    op.drop_column("chats", "task_id")
    op.create_foreign_key(
        "chats_session_task_id_fkey", "chats", "sessions", ["session_task_id"], ["task_id"], ondelete="CASCADE"
    )
    op.create_foreign_key("chats_project_id_fkey", "chats", "projects", ["project_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("chats_user_id_fkey", "chats", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_unique_constraint("uq_chats_session_task_id", "chats", ["session_task_id"])
    op.create_index("ix_chats_user_id", "chats", ["user_id"], unique=False)
    op.create_index("ix_chats_project_id", "chats", ["project_id"], unique=False)

    op.drop_index("uq_messages_external_id", table_name="messages")
    op.drop_index("ix_messages_parent_id", table_name="messages")
    op.drop_index("ix_messages_task_id", table_name="messages")
    op.drop_table("messages")
    op.drop_table("linear_tasks")
    op.drop_index("ix_tasks_project_id", table_name="tasks")
    op.drop_index("ix_tasks_kind", table_name="tasks")
    op.drop_table("tasks")
