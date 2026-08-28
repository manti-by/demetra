import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from migrations.versions.e5f6a7b8c9d0_seed_linear_defaults_into_user_environment import (
    _linear_default_rows,
    downgrade,
)


def _seed_table(connection) -> None:
    connection.execute(
        sa.text(
            "CREATE TABLE project_environment ("
            "id TEXT PRIMARY KEY, user_id TEXT, key TEXT, value TEXT, type TEXT, scope TEXT)"
        )
    )


def _insert(connection, row_id: str, user_id: str, key: str, value: str) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO project_environment (id, user_id, key, value, type, scope) "
            "VALUES (:id, :user_id, :key, :value, 'text', 'user')"
        ),
        {"id": row_id, "user_id": user_id, "key": key, "value": value},
    )


def test_downgrade_deletes_only_seeded_linear_keys():
    seeded_keys = [key for key, _ in _linear_default_rows()]
    assert seeded_keys, "expected at least one seeded LINEAR key in the test environment"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _seed_table(connection)
        _insert(connection, "seed-1", "u1", seeded_keys[0], "seeded")
        _insert(connection, "user-1", "u1", "LINEAR_FOO", "custom")

        ctx = MigrationContext.configure(connection)
        with Operations.context(ctx):
            downgrade()

        remaining = connection.execute(
            sa.text("SELECT key FROM project_environment WHERE scope = 'user' ORDER BY key")
        ).fetchall()

    assert [row[0] for row in remaining] == ["LINEAR_FOO"]


def test_downgrade_removes_every_seeded_key():
    seeded_keys = [key for key, _ in _linear_default_rows()]
    assert seeded_keys, "expected at least one seeded LINEAR key in the test environment"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _seed_table(connection)
        for index, key in enumerate(seeded_keys):
            _insert(connection, f"seed-{index}", "u1", key, "seeded")

        ctx = MigrationContext.configure(connection)
        with Operations.context(ctx):
            downgrade()

        remaining = connection.execute(
            sa.text("SELECT key FROM project_environment WHERE scope = 'user' ORDER BY key")
        ).fetchall()

    assert remaining == []
