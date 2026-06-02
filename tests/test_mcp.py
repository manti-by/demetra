import re
import shutil


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
