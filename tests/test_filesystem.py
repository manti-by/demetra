from pathlib import Path
from unittest.mock import patch

import pytest


class TestFilesystemService:
    def test_get_project_root_returns_correct_path(self):
        from demetra.services.filesystem import get_project_root

        with (
            patch("demetra.services.filesystem.os") as mock_os,
            patch("demetra.services.filesystem.PROJECTS_PATH", Path("/fake/www")),
        ):
            mock_os.listdir.return_value = ["project_a", "project_b", "project_c"]
            result = get_project_root("project_b")
            assert result == Path("/fake/www/project_b")

    def test_get_project_root_raises_for_missing_project(self):
        from demetra.services.filesystem import get_project_root

        with (
            patch("demetra.services.filesystem.os") as mock_os,
            patch("demetra.services.filesystem.PROJECTS_PATH", Path("/fake/www")),
        ):
            mock_os.listdir.return_value = ["other_project"]
            with pytest.raises(ValueError, match="not found"):
                get_project_root("missing_project")

    def test_get_project_root_uses_custom_projects_path(self):
        from demetra.services.filesystem import get_project_root

        with patch("demetra.services.filesystem.os") as mock_os:
            mock_os.listdir.return_value = ["myproject"]
            with patch("demetra.services.filesystem.PROJECTS_PATH", Path("/custom/path")):
                result = get_project_root("myproject")
                assert result == Path("/custom/path/myproject")
