from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from demetra.services.runtime.project import bump_project_version, create_postgres_role_and_database


SAMPLE_PYPROJECT = """[project]
name = "demetra"
version = "1.14.1"
description = "Coding workflow orchestration tool"
requires-python = ">=3.13.9,<3.14.0"
dependencies = []
"""


class TestBumpProjectVersion:
    def test_minor_bump(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(SAMPLE_PYPROJECT)

        result = bump_project_version(tmp_path)

        assert result == "1.15.0"
        content = pyproject.read_text()
        assert 'version = "1.15.0"' in content

    def test_major_version_preserved(self, tmp_path: Path):
        content = SAMPLE_PYPROJECT.replace('version = "1.14.1"', 'version = "2.14.1"')
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        result = bump_project_version(tmp_path)

        assert result == "2.15.0"
        content = pyproject.read_text()
        assert 'version = "2.15.0"' in content

    def test_preserves_other_fields(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(SAMPLE_PYPROJECT)

        _ = bump_project_version(tmp_path)
        content = pyproject.read_text()

        assert 'name = "demetra"' in content
        assert "requires-python" in content
        assert "dependencies" in content

    def test_missing_version_field_returns_none(self, tmp_path: Path):
        content = """[project]
name = "demetra"
"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        result = bump_project_version(tmp_path)
        assert result is None

    def test_invalid_version_format_returns_none(self, tmp_path: Path):
        content = SAMPLE_PYPROJECT.replace('version = "1.14.1"', 'version = "abc"')
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        result = bump_project_version(tmp_path)
        assert result is None


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConnection:
    def __init__(self, role_exists: bool):
        self.role_exists = role_exists
        self.statements: list[str] = []

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.statements.append(sql)
        if "SELECT 1 FROM pg_roles" in sql:
            return _FakeResult((1,) if self.role_exists else None)
        if "SELECT 1 FROM pg_database" in sql:
            return _FakeResult((1,))
        return _FakeResult(None)

    async def commit(self):
        pass


def _connection_factory(fake_connection: _FakeConnection):
    @asynccontextmanager
    async def _get_connection(db_name: str | None = None):
        yield fake_connection

    return _get_connection


class TestCreatePostgresRoleAndDatabase:
    PROJECT = {"repository_name": "demo", "id": "11111111-1111-1111-1111-111111111111"}

    @pytest.mark.asyncio
    async def test_existing_role_password_is_rotated_to_match_return_value(self):
        fake_connection = _FakeConnection(role_exists=True)
        with patch("demetra.services.runtime.project.get_connection", _connection_factory(fake_connection)):
            _, _, password = await create_postgres_role_and_database(self.PROJECT)

        assert any("ALTER ROLE" in stmt and password in stmt for stmt in fake_connection.statements)

    @pytest.mark.asyncio
    async def test_password_differs_between_calls(self):
        fake_connection_1 = _FakeConnection(role_exists=False)
        with patch("demetra.services.runtime.project.get_connection", _connection_factory(fake_connection_1)):
            _, _, password_1 = await create_postgres_role_and_database(self.PROJECT)

        fake_connection_2 = _FakeConnection(role_exists=True)
        with patch("demetra.services.runtime.project.get_connection", _connection_factory(fake_connection_2)):
            _, _, password_2 = await create_postgres_role_and_database(self.PROJECT)

        assert password_1 != password_2
        assert password_1 != self.PROJECT["repository_name"]
