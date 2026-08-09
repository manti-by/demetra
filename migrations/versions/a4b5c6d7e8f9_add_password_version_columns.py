"""add_password_version_columns

Revision ID: a4b5c6d7e8f9
Revises: d1e2f3a4b5c6
Create Date: 2026-08-09 23:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4b5c6d7e8f9"
down_revision: str | Sequence[str] | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("password_version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("jwt_tokens", sa.Column("password_version", sa.Integer(), server_default="1", nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("jwt_tokens", "password_version")
    op.drop_column("users", "password_version")
