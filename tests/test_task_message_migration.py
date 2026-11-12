"""Tests for the task/message schema migration.

The migration is Postgres-only (JSONB columns, a partial unique index and
named foreign keys), so the probe runs it against a dedicated schema in the
test database instead of the SQLite in-memory engine used by the other
migration tests.
"""

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from migrations.versions.a9b0c1d2e3f4_add_tasks_and_messages_tables import downgrade, upgrade

from demetra.settings import DATABASE


PROBE_SCHEMA = "task_message_migration_probe"

PRE_MIGRATION_SCHEMA = """
CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT);
CREATE TABLE projects (id TEXT PRIMARY KEY, user_id TEXT, name TEXT);
CREATE TABLE sessions (
    task_id TEXT PRIMARY KEY,
    name TEXT,
    build_plan TEXT DEFAULT '',
    posted_to_linear BOOLEAN DEFAULT false,
    step TEXT DEFAULT 'initial',
    is_research BOOLEAN DEFAULT false,
    project_id TEXT,
    user_id TEXT,
    run_attempts INTEGER DEFAULT 0,
    listener_attempts INTEGER DEFAULT 0,
    pr_link TEXT,
    linear_link TEXT,
    research_report TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE chats (
    id SERIAL PRIMARY KEY,
    session_task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    tags JSONB DEFAULT '[]',
    user_id TEXT,
    project_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_chats_session_task_id UNIQUE (session_task_id),
    CONSTRAINT chats_session_task_id_fkey FOREIGN KEY (session_task_id) REFERENCES sessions (task_id) ON DELETE CASCADE,
    CONSTRAINT chats_user_id_fkey FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT chats_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
);
CREATE INDEX ix_chats_user_id ON chats (user_id);
CREATE INDEX ix_chats_project_id ON chats (project_id);
CREATE TABLE chat_messages (
    id TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    session_task_id TEXT NOT NULL,
    author_id TEXT,
    is_system BOOLEAN DEFAULT false,
    kind TEXT DEFAULT 'message',
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chat_messages_chat_id_fkey FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE,
    CONSTRAINT chat_messages_author_id_fkey FOREIGN KEY (author_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_chat_messages_session_task_id ON chat_messages (session_task_id);
"""

SEED_ROWS = """
INSERT INTO users (id, email) VALUES ('user-1', 'a@example.com');
INSERT INTO projects (id, user_id, name) VALUES ('project-1', 'user-1', 'demetra');
INSERT INTO sessions (task_id, name, step, project_id, user_id)
VALUES ('11111111-1111-1111-1111-111111111111', 'MNT-312: Unify task model', 'completed', 'project-1', 'user-1');
INSERT INTO sessions (task_id, name, step, project_id, user_id)
VALUES ('CH-1', 'CH-1: Chat about auth', 'completed', 'project-1', 'user-1');
INSERT INTO chats (id, session_task_id, title, description, tags, user_id, project_id)
VALUES (1, 'CH-1', 'Chat about auth', 'Please help with auth', '["backend"]', 'user-1', 'project-1');
INSERT INTO chat_messages (id, chat_id, session_task_id, author_id, is_system, kind, body)
VALUES ('msg-1', 1, 'CH-1', 'user-1', false, 'message', 'How do I add auth?');
"""


def _sync_url() -> str:
    """Return the connection URL of the test database.

    Returns:
        str: The psycopg connection URL.
    """
    return (
        f"postgresql+psycopg://{DATABASE['user']}:{DATABASE['password']}"
        f"@{DATABASE['host']}:{DATABASE['port']}/{DATABASE['name']}"
    )


def _run_statements(connection, script: str) -> None:
    """Execute the statements of a script.

    Args:
        connection: The connection to run the statements on.
        script: The semicolon-separated SQL script.
    """
    for statement in script.strip().split(";"):
        if statement.strip():
            connection.execute(text(statement))


def _seed_probe(connection) -> None:
    """Create the pre-migration schema and seed it.

    Args:
        connection: The connection bound to the probe schema.
    """
    connection.execute(text(f"DROP SCHEMA IF EXISTS {PROBE_SCHEMA} CASCADE"))
    connection.execute(text(f"CREATE SCHEMA {PROBE_SCHEMA}"))
    connection.execute(text(f"SET search_path TO {PROBE_SCHEMA}"))
    _run_statements(connection, PRE_MIGRATION_SCHEMA)
    _run_statements(connection, SEED_ROWS)


def _run_migration(connection, migration) -> None:
    """Run a migration revision against the probe schema.

    Args:
        connection: The connection bound to the probe schema.
        migration: The ``upgrade`` or ``downgrade`` callable of the revision.
    """
    ctx = MigrationContext.configure(connection)
    with Operations.context(ctx):
        migration()


class TestTaskMessageMigration:
    @pytest.mark.asyncio
    async def test_upgrade_backfills_tasks_and_messages(self, setup_test_db):
        engine = create_engine(_sync_url())
        with engine.begin() as connection:
            _seed_probe(connection)
            _run_migration(connection, upgrade)

            tasks = connection.execute(
                text("SELECT id, kind, identifier, title, state, tags FROM tasks ORDER BY kind")
            ).fetchall()
            messages = connection.execute(text("SELECT id, task_id, source, kind, body FROM messages")).fetchall()
            chats = connection.execute(text("SELECT id, task_id FROM chats")).fetchall()
        engine.dispose()

        assert tasks == [
            ("CH-1", "chat", "CH-1", "Chat about auth", "completed", ["backend"]),
            (
                "11111111-1111-1111-1111-111111111111",
                "linear",
                "MNT-312",
                "Unify task model",
                "completed",
                [],
            ),
        ]
        assert messages == [("msg-1", "CH-1", "chat", "message", "How do I add auth?")]
        assert chats == [(1, "CH-1")]

    @pytest.mark.asyncio
    async def test_downgrade_restores_the_previous_tables(self, setup_test_db):
        engine = create_engine(_sync_url())
        with engine.begin() as connection:
            _seed_probe(connection)
            _run_migration(connection, upgrade)
            _run_migration(connection, downgrade)

            chats = connection.execute(text("SELECT session_task_id, title, tags FROM chats")).fetchall()
            messages = connection.execute(
                text("SELECT id, chat_id, session_task_id, body FROM chat_messages")
            ).fetchall()
        engine.dispose()

        assert chats == [("CH-1", "Chat about auth", ["backend"])]
        assert messages == [("msg-1", 1, "CH-1", "How do I add auth?")]

    @pytest.mark.asyncio
    async def test_downgrade_maps_a_comment_kind_back_to_a_legacy_kind(self, setup_test_db):
        engine = create_engine(_sync_url())
        with engine.begin() as connection:
            _seed_probe(connection)
            _run_migration(connection, upgrade)
            connection.execute(
                text(
                    "INSERT INTO messages (id, task_id, parent_id, source, external_id, author_id, "
                    "author_name, is_system, kind, body, created_at) "
                    "VALUES ('msg-2', 'CH-1', NULL, 'chat', NULL, NULL, NULL, false, 'comment', "
                    "'A comment', NOW())"
                )
            )
            _run_migration(connection, downgrade)

            kinds = connection.execute(text("SELECT id, kind FROM chat_messages ORDER BY id")).fetchall()
        engine.dispose()

        assert kinds == [("msg-1", "message"), ("msg-2", "message")]
