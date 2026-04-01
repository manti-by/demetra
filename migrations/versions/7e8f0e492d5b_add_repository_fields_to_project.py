"""Add repository fields to Project

Revision ID: 7e8f0e492d5b
Revises: b2c3d4e5f678
Create Date: 2026-04-01 17:21:09.343139

"""

from collections.abc import Sequence


from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7e8f0e492d5b"
down_revision: str | Sequence[str] | None = "b2c3d4e5f678"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("projects", sa.Column("repository_name", sa.String(), nullable=True))
    op.add_column("projects", sa.Column("repository_owner", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("projects", "repository_name")
    op.drop_column("projects", "repository_owner")
