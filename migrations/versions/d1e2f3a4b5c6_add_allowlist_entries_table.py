"""add_allowlist_entries_table

Revision ID: d1e2f3a4b5c6
Revises: b1c2d3e4f5a6
Create Date: 2026-08-04 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "allowlist_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("entry_type", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("added_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_type", "value", name="uq_allowlist_entries_type_value"),
        sa.CheckConstraint("entry_type IN ('email', 'github_username')", name="ck_allowlist_entries_type"),
    )
    op.create_index("ix_allowlist_entries_value", "allowlist_entries", ["value"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_allowlist_entries_value", table_name="allowlist_entries")
    op.drop_table("allowlist_entries")
