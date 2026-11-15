import re
import shutil

import pytest

from demetra.mcp_server import main


class TestMcpServerFailFast:
    async def test_exits_when_db_password_is_missing(self, monkeypatch):
        monkeypatch.setattr(
            "demetra.mcp_server.DATABASE",
            {"host": "localhost", "port": 5432, "user": "demetra", "name": "demetra", "password": None},
        )

        with pytest.raises(RuntimeError, match="DB_PASSWORD"):
            await main()

    async def test_starts_when_a_password_is_configured(self, monkeypatch):
        monkeypatch.setattr(
            "demetra.mcp_server.DATABASE",
            {"host": "localhost", "port": 5432, "user": "demetra", "name": "demetra", "password": "secret"},
        )

        class StartupReachedError(Exception):
            pass

        entered = []

        class FakeStdioServer:
            async def __aenter__(self):
                entered.append(True)
                raise StartupReachedError

            async def __aexit__(self, exc_type, exc, traceback):
                return False

        monkeypatch.setattr("demetra.mcp_server.stdio_server", FakeStdioServer)

        with pytest.raises(StartupReachedError):
            await main()

        assert entered == [True]


class TestTableNameValidation:
    def test_valid_table_names(self):
        _TABLE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
        valid_names = ["users", "user_profiles", "TestTable", "_private", "table123"]
        for name in valid_names:
            assert _TABLE_NAME_RE.match(name), f"Expected {name} to be valid"

    def test_invalid_table_names_rejected(self):
        _TABLE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
        invalid_names = [
            "invalid key",
            "'; DROP TABLE users; --",
            "123table",
            "table-name",
            "table.name",
        ]
        for name in invalid_names:
            assert not _TABLE_NAME_RE.match(name), f"Expected {name} to be invalid"

    def test_sql_injection_filter_key_rejected(self):
        _TABLE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
        sql_injection_attempts = [
            "'; DELETE FROM users; --",
            'id" = 1; DROP TABLE users; --',
            "col` = `value`",
            'column" = $1; malicious SQL',
        ]
        for attempt in sql_injection_attempts:
            assert not _TABLE_NAME_RE.match(attempt), f"Expected SQL injection '{attempt}' to be rejected"


class TestDeleteFile:
    def test_rmtree_removes_non_empty_directory(self, tmp_path):
        test_dir = tmp_path / "subdir"
        test_dir.mkdir()
        (test_dir / "nested.txt").write_text("content")
        shutil.rmtree(test_dir)
        assert not test_dir.exists()
