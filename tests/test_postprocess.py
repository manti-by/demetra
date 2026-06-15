from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.workflows.postprocess import postprocess_with_ruff


class TestPostprocess:
    target_path = Path("/test/path")

    @pytest.fixture
    def ruff_mocks(self):
        with (
            patch("demetra.workflows.postprocess.is_package_installed", new_callable=AsyncMock) as mock_pkg,
            patch("demetra.workflows.postprocess.run_ruff_format", new_callable=AsyncMock) as mock_format,
            patch("demetra.workflows.postprocess.run_ruff_fix", new_callable=AsyncMock) as mock_fix,
            patch("demetra.workflows.postprocess.run_ruff_check_diff", new_callable=AsyncMock) as mock_diff,
        ):
            yield mock_pkg, mock_format, mock_fix, mock_diff

    @pytest.fixture
    def mock_pkg(self):
        with patch("demetra.workflows.postprocess.is_package_installed", new_callable=AsyncMock) as m:
            yield m

    @pytest.mark.asyncio
    async def test_clean(self, ruff_mocks):
        mock_pkg, mock_format, mock_fix, mock_diff = ruff_mocks
        mock_pkg.return_value = True
        mock_format.return_value = (0, "", "")
        mock_fix.return_value = (0, "", "")
        mock_diff.return_value = (0, "", "")
        has_issues, feedback = await postprocess_with_ruff(target_path=self.target_path)
        assert has_issues is False
        assert feedback is None
        mock_format.assert_awaited_once_with(target_path=self.target_path, env=None)
        mock_fix.assert_awaited_once_with(target_path=self.target_path, env=None)
        mock_diff.assert_awaited_once_with(target_path=self.target_path, env=None)

    @pytest.mark.asyncio
    async def test_with_remaining_issues(self, ruff_mocks):
        mock_pkg, mock_format, mock_fix, mock_diff = ruff_mocks
        ruff_diff = "file.py:10:5: B006 Do not use mutable data structures for argument defaults"
        mock_pkg.return_value = True
        mock_format.return_value = (0, "", "")
        mock_fix.return_value = (0, "", "")
        mock_diff.return_value = (1, ruff_diff, "")
        has_issues, feedback = await postprocess_with_ruff(target_path=self.target_path)
        assert has_issues is True
        assert feedback == ruff_diff

    @pytest.mark.asyncio
    async def test_ruff_not_installed(self, mock_pkg):
        mock_pkg.return_value = False
        has_issues, feedback = await postprocess_with_ruff(target_path=self.target_path)
        assert has_issues is False
        assert feedback is None
