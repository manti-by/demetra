"""Collapse task_status into sessions

Revision ID: qbof4yrxlne2
Revises: 556019e457d2
Create Date: 2026-04-01

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "qbof4yrxlne2"
down_revision: str | Sequence[str] | None = "556019e457d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Collapse task_status into sessions and remove task_status table."""
    op.add_column("sessions", sa.Column("status", sa.String(), server_default="pending", nullable=False))
    op.add_column("sessions", sa.Column("project_id", sa.String(), nullable=True))
    op.add_column("sessions", sa.Column("user_id", sa.String(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE sessions s
            SET
                status = COALESCE(ts.status, 'pending'),
                project_id = p.id,
                user_id = p.user_id
            FROM task_status ts
            LEFT JOIN projects p ON LOWER(p.name) = LOWER(ts.project_name)
            WHERE s.task_id = ts.task_id
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE sessions s
            SET status = 'pending'
            WHERE s.status IS NULL OR s.status = ''
            """
        )
    )

    op.drop_table("task_status")


def downgrade() -> None:
    """Restore task_status table from sessions."""
    op.create_table(
        "task_status",
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("project_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("task_id"),
    )

    op.alter_column("sessions", "status", nullable=True)
    op.alter_column("sessions", "project_id", nullable=True)
    op.alter_column("sessions", "user_id", nullable=True)
