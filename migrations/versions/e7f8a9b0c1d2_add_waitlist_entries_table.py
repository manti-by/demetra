"""add_waitlist_entries_table

Revision ID: e7f8a9b0c1d2
Revises: e5f6a7b8c9d0
Create Date: 2026-08-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "waitlist_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("entry_type", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_type", "value", name="uq_waitlist_entries_type_value"),
        sa.CheckConstraint("entry_type IN ('email', 'github_username')", name="ck_waitlist_entries_type"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'joined')", name="ck_waitlist_entries_status"
        ),
    )
    op.create_index("ix_waitlist_entries_value", "waitlist_entries", ["value"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_waitlist_entries_value", table_name="waitlist_entries")
    op.drop_table("waitlist_entries")
