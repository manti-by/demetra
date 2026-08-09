import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from demetra.services.runtime.filesystem import get_project_root


class TestFilesystemService:
    def test_get_project_root_returns_correct_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = Path(tmpdir)
            (projects_path / "project_a").mkdir()
            (projects_path / "project_b").mkdir()
            (projects_path / "project_c").mkdir()
            with patch("demetra.services.runtime.filesystem.PROJECTS_PATH", projects_path):
                result = get_project_root("project_b")
                assert result == projects_path / "project_b"

    def test_get_project_root_raises_for_missing_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = Path(tmpdir)
            (projects_path / "other_project").mkdir()
            with patch("demetra.services.runtime.filesystem.PROJECTS_PATH", projects_path):
                with pytest.raises(Exception, match="not found"):
                    get_project_root("missing_project")

    def test_get_project_root_uses_custom_projects_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = Path(tmpdir)
            (projects_path / "myproject").mkdir()
            with patch("demetra.services.runtime.filesystem.PROJECTS_PATH", projects_path):
                result = get_project_root("myproject")
                assert result == projects_path / "myproject"

    def test_get_project_root_raises_when_projects_path_missing(self):
        with patch("demetra.services.runtime.filesystem.PROJECTS_PATH", Path("/nonexistent/path")):
            with pytest.raises(Exception, match="does not exist"):
                get_project_root("whatever")

    def test_get_project_root_raises_when_projects_path_not_dir(self):
        with tempfile.NamedTemporaryFile() as tmpfile:
            file_path = Path(tmpfile.name)
            with patch("demetra.services.runtime.filesystem.PROJECTS_PATH", file_path):
                with pytest.raises(Exception, match="not a directory"):
                    get_project_root("whatever")
