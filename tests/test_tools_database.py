from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from demetra import settings
from demetra.services.persistence import database as persistence_database
from demetra.tools import database


TEST_PREFIX = "test-mcp-"


async def _insert_project(pool: asyncpg.Pool, *, project_id: str, name: str = "project") -> None:
    await pool.execute(
        """
        INSERT INTO projects (id, user_id, name, repository_url, repository_name, repository_owner, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, now(), now())
        """,
        project_id,
        f"{TEST_PREFIX}user",
        name,
        "https://github.com/manti-by/demetra",
        "demetra",
        "manti-by",
    )


@pytest_asyncio.fixture
async def pool(monkeypatch):
    """Provide the shared MCP pool pointed at the suite's test database.

    ``get_db_pool`` reads ``demetra.settings.DATABASE`` at call time and refuses
    to build a pool without a password, which CI supplies as ``demetra``. The
    session fixture points the persistence module at ``test_demetra`` and tests
    that reload ``demetra.settings`` replace its ``DATABASE`` object, so the
    resolved credentials are re-applied from the persistence module here.

    Args:
        monkeypatch: The pytest fixture used to patch the resolved settings.
    """
    await database.close_db_pool()
    database.allowed_tables = None
    credentials = persistence_database.DATABASE
    monkeypatch.setattr(
        settings,
        "DATABASE",
        {**credentials, "password": credentials["password"] or "demetra"},
    )
    created = await database.get_db_pool()
    yield created
    await created.execute("DELETE FROM projects WHERE id LIKE $1", f"{TEST_PREFIX}%")
    await created.execute("DELETE FROM oauth_tokens WHERE service LIKE $1", f"{TEST_PREFIX}%")
    await database.close_db_pool()
    database.allowed_tables = None


class TestQuoteIdentifier:
    def test_wraps_plain_name(self):
        assert database._quote_identifier("projects") == '"projects"'

    def test_escapes_embedded_quotes(self):
        assert database._quote_identifier('we"ird') == '"we""ird"'


class TestGetTableCount:
    @pytest.mark.asyncio
    async def test_counts_the_rows_of_a_table(self, pool: asyncpg.Pool):
        project_ids = [f"{TEST_PREFIX}{uuid4().hex[:8]}" for _ in range(3)]
        for project_id in project_ids:
            await _insert_project(pool=pool, project_id=project_id)

        result = await database.get_table_count(pool=pool, table_name="projects")

        expected = await pool.fetchval("SELECT COUNT(*) FROM projects")
        assert result == {"table_name": "projects", "count": expected}
        assert result["count"] >= 3

    @pytest.mark.asyncio
    async def test_rejects_unknown_table(self, pool: asyncpg.Pool):
        with pytest.raises(ValueError, match="Table not found"):
            await database.get_table_count(pool=pool, table_name="missing_table")


class TestQueryTable:
    @pytest.mark.asyncio
    async def test_returns_rows_with_the_table_columns(self, pool: asyncpg.Pool):
        project_ids = [f"{TEST_PREFIX}{uuid4().hex[:8]}" for _ in range(2)]
        for project_id in project_ids:
            await _insert_project(pool=pool, project_id=project_id)

        rows = await database.query_table(
            pool=pool,
            table_name="projects",
            filters={"user_id": f"{TEST_PREFIX}user"},
            limit=10,
        )

        assert {row["id"] for row in rows} == set(project_ids)
        assert "quote_ident" not in rows[0]
        assert "name" in rows[0]

    @pytest.mark.asyncio
    async def test_filters_by_column(self, pool: asyncpg.Pool):
        first = f"{TEST_PREFIX}{uuid4().hex[:8]}"
        second = f"{TEST_PREFIX}{uuid4().hex[:8]}"
        await _insert_project(pool=pool, project_id=first)
        await _insert_project(pool=pool, project_id=second)

        rows = await database.query_table(pool=pool, table_name="projects", filters={"id": first})

        assert [row["id"] for row in rows] == [first]

    @pytest.mark.asyncio
    async def test_respects_limit_and_offset(self, pool: asyncpg.Pool):
        project_ids = [f"{TEST_PREFIX}{uuid4().hex[:8]}" for _ in range(3)]
        for project_id in project_ids:
            await _insert_project(pool=pool, project_id=project_id)

        rows = await database.query_table(
            pool=pool,
            table_name="projects",
            filters={"user_id": f"{TEST_PREFIX}user"},
            limit=2,
            offset=1,
        )

        assert len(rows) == 2
        assert {row["id"] for row in rows} <= set(project_ids)

    @pytest.mark.asyncio
    async def test_strips_sensitive_columns(self, pool: asyncpg.Pool):
        await pool.execute(
            "INSERT INTO oauth_tokens (service, access_token, refresh_token, expires_at) VALUES ($1, $2, $3, now())",
            f"{TEST_PREFIX}github",
            "access-token-value",
            "refresh-token-value",
        )

        rows = await database.query_table(
            pool=pool,
            table_name="oauth_tokens",
            filters={"service": f"{TEST_PREFIX}github"},
        )

        assert len(rows) == 1
        assert set(rows[0]) == {"service", "expires_at"}

    @pytest.mark.asyncio
    async def test_rejects_unknown_column(self, pool: asyncpg.Pool):
        with pytest.raises(ValueError, match="Column not found"):
            await database.query_table(pool=pool, table_name="projects", filters={"missing": "value"})

    @pytest.mark.asyncio
    async def test_rejects_unknown_table(self, pool: asyncpg.Pool):
        with pytest.raises(ValueError, match="Table not found"):
            await database.query_table(pool=pool, table_name="missing_table")


class TestCallToolErrors:
    @pytest.mark.asyncio
    async def test_error_result_includes_the_underlying_cause(self, monkeypatch):
        async def _fail():
            raise ValueError("DB_PASSWORD environment variable is required")

        monkeypatch.setattr(database, "get_db_pool", _fail)

        result = await database.call_tool("list_tables", None)

        assert result.is_error is True
        assert "Database operation failed" in result.content[0].text
        assert "DB_PASSWORD environment variable is required" in result.content[0].text

    @pytest.mark.asyncio
    async def test_unknown_tool_is_reported(self):
        result = await database.call_tool("missing_tool", None)

        assert result.is_error is True
        assert "Unknown tool missing_tool" in result.content[0].text
