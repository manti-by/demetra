"""seed_linear_defaults_into_user_environment

Revision ID: e5f6a7b8c9d0
Revises: a6b7c8d9e0f1
Create Date: 2026-08-18 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

from demetra.settings import LINEAR

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "a6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _linear_default_rows() -> list[tuple[str, str]]:
    """Return the LINEAR env keys paired with their settings defaults."""
    rows = [("LINEAR_TEAM_ID", LINEAR["team_id"]), ("LINEAR_DEFAULT_STATE_ID", LINEAR["default_state"])]
    rows.extend((f"LINEAR_STATE_{name.upper()}_ID", state_id) for name, state_id in LINEAR["states"].items())
    return [(key, value) for key, value in rows if isinstance(value, str)]


def upgrade() -> None:
    """Seed the LINEAR settings defaults as user-shared environment rows.

    Every existing user gets the current ``settings.LINEAR`` defaults as
    ``scope = 'user'`` rows so the resolver can read them without a settings
    change. Rows a user already set are left untouched.
    """
    for key, value in _linear_default_rows():
        op.execute(
            sa.text(
                """
                INSERT INTO project_environment (id, user_id, key, value, type, scope)
                SELECT gen_random_uuid()::text, users.id, :key, :value, 'text', 'user'
                FROM users
                ON CONFLICT (user_id, key) WHERE user_id IS NOT NULL DO NOTHING
                """
            ).bindparams(key=key, value=value)
        )


def downgrade() -> None:
    """Remove the seeded LINEAR defaults from user-shared environment rows."""
    op.execute(sa.text("DELETE FROM project_environment WHERE scope = 'user' AND key LIKE 'LINEAR_%'"))
