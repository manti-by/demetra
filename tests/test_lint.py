from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.quality.lint import run_ruff_check_diff, run_ruff_checks, run_ruff_fix


class TestLintService:
    @pytest.fixture
    def mock_run_command(self):
        with patch("demetra.services.quality.lint.run_command", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_ruff_checks_success(self, mock_run_command):
        """Test successful ruff check execution."""
        target_path = Path("/test/path")
        mock_run_command.return_value = (0, "ruff check output", "")
        result = await run_ruff_checks(target_path=target_path)

        assert mock_run_command.call_count == 1
        call = mock_run_command.call_args
        assert call[1]["command"][1:] == ["run", "--active", "ruff", "check", "--quiet"]
        assert call[1]["target_path"] == target_path
        assert result == (0, "ruff check output", "")

    @pytest.mark.asyncio
    async def test_ruff_checks_failure(self, mock_run_command):
        """Test ruff check when command fails."""
        target_path = Path("/test/path")
        mock_run_command.side_effect = Exception("ruff check failed")

        with pytest.raises(Exception, match="ruff check failed"):
            await run_ruff_checks(target_path=target_path)

        assert mock_run_command.call_count == 1

    @pytest.mark.asyncio
    async def test_ruff_checks_no_session(self, mock_run_command):
        """Test ruff check without session ID."""
        target_path = Path("/test/path")
        mock_run_command.return_value = (0, "ruff check output", "")
        result = await run_ruff_checks(target_path=target_path)

        assert mock_run_command.call_count == 1
        assert result == (0, "ruff check output", "")

    @pytest.mark.asyncio
    async def test_ruff_fix_success(self, mock_run_command):
        """Test successful ruff check --fix execution."""
        target_path = Path("/test/path")
        mock_run_command.return_value = (0, "3 fixed, 0 remaining", "")
        result = await run_ruff_fix(target_path=target_path)

        assert mock_run_command.call_count == 1
        call = mock_run_command.call_args
        assert call[1]["command"][1:] == ["run", "--active", "ruff", "check", "--fix", "--quiet"]
        assert call[1]["target_path"] == target_path
        assert result == (0, "3 fixed, 0 remaining", "")

    @pytest.mark.asyncio
    async def test_ruff_fix_remaining_issues(self, mock_run_command):
        """Test ruff --fix when some issues remain unfixed."""
        target_path = Path("/test/path")
        mock_run_command.return_value = (1, "1 fixed, 2 remaining", "")
        result = await run_ruff_fix(target_path=target_path)

        assert result == (1, "1 fixed, 2 remaining", "")

    @pytest.mark.asyncio
    async def test_ruff_check_diff_success(self, mock_run_command):
        """Test successful ruff check --diff execution."""
        target_path = Path("/test/path")
        mock_run_command.return_value = (1, "file.py:10:5: B006 ...", "")
        result = await run_ruff_check_diff(target_path=target_path)

        assert mock_run_command.call_count == 1
        call = mock_run_command.call_args
        assert call[1]["command"][1:] == [
            "run",
            "--active",
            "ruff",
            "check",
            "--diff",
            "--output-format=concise",
        ]
        assert call[1]["target_path"] == target_path
        assert result == (1, "file.py:10:5: B006 ...", "")
