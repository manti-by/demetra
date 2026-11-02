"""create_chats_and_chat_messages_tables

Revision ID: b8f1c2d3e4a5
Revises: f2a3b4c5d6e7
Create Date: 2026-10-31 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8f1c2d3e4a5"
down_revision: str | Sequence[str] | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "chats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_task_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("tags", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_task_id"], ["sessions.task_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_task_id", name="uq_chats_session_task_id"),
    )
    op.create_index("ix_chats_user_id", "chats", ["user_id"], unique=False)
    op.create_index("ix_chats_project_id", "chats", ["project_id"], unique=False)

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


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_chat_messages_session_task_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chats_project_id", table_name="chats")
    op.drop_index("ix_chats_user_id", table_name="chats")
    op.drop_table("chats")
