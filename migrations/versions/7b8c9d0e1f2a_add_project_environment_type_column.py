"""add_project_environment_type_column

Revision ID: 7b8c9d0e1f2a
Revises: a1b2c3d4e5f6
Create Date: 2026-06-10 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b8c9d0e1f2a"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "project_environment",
        sa.Column(
            "type",
            sa.String(),
            nullable=False,
            server_default="text",
        ),
    )
    op.create_check_constraint(
        "ck_project_environment_type",
        "project_environment",
        "type IN ('text', 'encrypted')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_project_environment_type", "project_environment", type_="check")
    op.drop_column("project_environment", "type")
