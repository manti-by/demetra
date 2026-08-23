from pathlib import Path

from demetra.services.runtime.project import bump_project_version


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
