from pathlib import Path

from demetra.services.project import bump_project_version, is_epic_label


class TestIsEpicLabel:
    def test_epic_label_uppercase(self):
        assert is_epic_label(["EPIC", "bug"]) is True

    def test_epic_label_lowercase(self):
        assert is_epic_label(["epic"]) is True

    def test_epic_label_capitalized(self):
        assert is_epic_label(["Epic"]) is True

    def test_non_epic_labels(self):
        assert is_epic_label(["bug", "frontend", "enhancement"]) is False

    def test_empty_labels(self):
        assert is_epic_label([]) is False


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

        result = bump_project_version(tmp_path, is_epic=False)

        assert result == "1.15.0"
        content = pyproject.read_text()
        assert 'version = "1.15.0"' in content

    def test_major_bump(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(SAMPLE_PYPROJECT)

        result = bump_project_version(tmp_path, is_epic=True)

        assert result == "2.0.0"
        content = pyproject.read_text()
        assert 'version = "2.0.0"' in content

    def test_preserves_other_fields(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(SAMPLE_PYPROJECT)

        _ = bump_project_version(tmp_path, is_epic=False)
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

        result = bump_project_version(tmp_path, is_epic=False)
        assert result is None

    def test_invalid_version_format_returns_none(self, tmp_path: Path):
        content = SAMPLE_PYPROJECT.replace('version = "1.14.1"', 'version = "abc"')
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(content)

        result = bump_project_version(tmp_path, is_epic=False)
        assert result is None
