"""normalize_empty_session_ids

An empty session id is not a resumable opencode session: passing it alongside
``--fork`` makes the CLI fail with ``--fork requires --continue or --session``.
Normalize ids left as ``''`` by earlier writers to NULL so every consumer sees
an absent id consistently.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-11-23 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b0c1d2e3f4a5"
down_revision: str | Sequence[str] | None = "a9b0c1d2e3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Normalize empty session ids to NULL."""
    op.execute(sa.text("UPDATE sessions SET session_id = NULL WHERE session_id = ''"))


def downgrade() -> None:
    """Leave normalized rows untouched.

    Once an empty id has become NULL it can no longer be distinguished from a
    session that was never attributed, so there is nothing to restore.
    """
