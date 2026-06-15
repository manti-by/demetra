import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from demetra.services.filesystem import get_project_root


class TestFilesystemService:
    def test_get_project_root_returns_correct_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = Path(tmpdir)
            (projects_path / "project_a").mkdir()
            (projects_path / "project_b").mkdir()
            (projects_path / "project_c").mkdir()
            with patch("demetra.services.filesystem.PROJECTS_PATH", projects_path):
                result = get_project_root("project_b")
                assert result == projects_path / "project_b"

    def test_get_project_root_raises_for_missing_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = Path(tmpdir)
            (projects_path / "other_project").mkdir()
            with patch("demetra.services.filesystem.PROJECTS_PATH", projects_path):
                with pytest.raises(Exception, match="not found"):
                    get_project_root("missing_project")

    def test_get_project_root_uses_custom_projects_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = Path(tmpdir)
            (projects_path / "myproject").mkdir()
            with patch("demetra.services.filesystem.PROJECTS_PATH", projects_path):
                result = get_project_root("myproject")
                assert result == projects_path / "myproject"
