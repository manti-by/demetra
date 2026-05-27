import re
import shutil

import pytest

from demetra.tools.filesystem import delete_file, list_directory, read_file, write_file


class TestFilesystemTools:
    @pytest.fixture
    def temp_cwd(self, tmp_path):
        test_dir = tmp_path / "test_project"
        test_dir.mkdir()
        (test_dir / "test_file.txt").write_text("test content")
        subdir = test_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested content")
        return test_dir

    @pytest.mark.asyncio
    async def test_read_file_success(self, temp_cwd):
        result = await read_file("test_file.txt", cwd=temp_cwd)
        assert len(result) == 1
        assert "test content" in result[0].text

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, temp_cwd):
        result = await read_file("nonexistent.txt", cwd=temp_cwd)
        assert "Error: File not found" in result[0].text

    @pytest.mark.asyncio
    async def test_read_file_path_outside_cwd(self, temp_cwd):
        result = await read_file("../../../etc/passwd", cwd=temp_cwd)
        assert "outside allowed directory" in result[0].text

    @pytest.mark.asyncio
    async def test_read_directory_error(self, temp_cwd):
        result = await read_file("subdir", cwd=temp_cwd)
        assert "directory" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_write_file_success(self, temp_cwd):
        result = await write_file("new_file.txt", "new content", cwd=temp_cwd)
        assert "Successfully wrote" in result[0].text
        assert (temp_cwd / "new_file.txt").read_text() == "new content"

    @pytest.mark.asyncio
    async def test_write_file_creates_parent_dirs(self, temp_cwd):
        result = await write_file("subdir/new/nested.txt", "nested", cwd=temp_cwd)
        assert "Successfully wrote" in result[0].text
        assert (temp_cwd / "subdir" / "new" / "nested.txt").read_text() == "nested"

    @pytest.mark.asyncio
    async def test_write_file_path_outside_cwd(self, temp_cwd):
        result = await write_file("../../../etc/test.txt", "content", cwd=temp_cwd)
        assert "outside allowed directory" in result[0].text

    @pytest.mark.asyncio
    async def test_delete_file_success(self, temp_cwd):
        test_file = temp_cwd / "to_delete.txt"
        test_file.write_text("to delete")

        result = await delete_file("to_delete.txt", cwd=temp_cwd)
        assert "Successfully deleted" in result[0].text
        assert not test_file.exists()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, temp_cwd):
        result = await delete_file("nonexistent.txt", cwd=temp_cwd)
        assert "File not found" in result[0].text

    @pytest.mark.asyncio
    async def test_delete_directory(self, temp_cwd):
        result = await delete_file("subdir", cwd=temp_cwd)
        assert "Successfully deleted" in result[0].text

    @pytest.mark.asyncio
    async def test_list_directory(self, temp_cwd):
        result = await list_directory("", cwd=temp_cwd)
        assert "test_file.txt" in result[0].text
        assert "subdir" in result[0].text

    @pytest.mark.asyncio
    async def test_list_subdirectory(self, temp_cwd):
        result = await list_directory("subdir", cwd=temp_cwd)
        assert "nested.txt" in result[0].text

    @pytest.mark.asyncio
    async def test_list_directory_not_found(self, temp_cwd):
        result = await list_directory("nonexistent", cwd=temp_cwd)
        assert "Directory not found" in result[0].text


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
