"""add_messages_answer_link

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-11-27 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


MESSAGES_KIND = "kind IN ('message', 'question', 'answer', 'plan', 'failure', 'research', 'status', 'comment')"
MESSAGES_KIND_PREVIOUS = "kind IN ('message', 'question', 'plan', 'failure', 'research', 'status', 'comment')"


def upgrade() -> None:
    """Link answer messages to their question and track consumed context."""
    op.add_column("messages", sa.Column("related_id", sa.String(), nullable=True))
    op.add_column(
        "messages",
        sa.Column("is_added_to_context", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_foreign_key(
        "messages_related_id_fkey",
        "messages",
        "messages",
        ["related_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_messages_related_id", "messages", ["related_id"])
    op.drop_constraint("ck_messages_kind", "messages", type_="check")
    op.create_check_constraint("ck_messages_kind", "messages", MESSAGES_KIND)


def downgrade() -> None:
    """Remove the answer link and restore the previous message kinds."""
    op.drop_constraint("ck_messages_kind", "messages", type_="check")
    op.create_check_constraint("ck_messages_kind", "messages", MESSAGES_KIND_PREVIOUS)
    op.drop_index("ix_messages_related_id", table_name="messages")
    op.drop_constraint("messages_related_id_fkey", "messages", type_="foreignkey")
    op.drop_column("messages", "is_added_to_context")
    op.drop_column("messages", "related_id")
