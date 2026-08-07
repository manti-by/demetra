from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.quality.lint import run_ruff_checks
from demetra.services.quality.test import run_pytests


@pytest.mark.asyncio
class TestIntegration:
    @pytest.fixture
    def mock_run_commands(self):
        with (
            patch("demetra.services.quality.lint.run_command", new_callable=AsyncMock) as mock_precommit,
            patch("demetra.services.quality.test.run_command", new_callable=AsyncMock) as mock_test,
        ):
            yield mock_precommit, mock_test

    @pytest.fixture
    def mock_run_precommit(self):
        with patch("demetra.services.quality.lint.run_command", new_callable=AsyncMock) as mock_precommit:
            yield mock_precommit

    async def test_precommit_and_test_integration(self, mock_run_commands):
        target_path = Path("/test/path")
        session_id = "test-session"

        mock_precommit, mock_test = mock_run_commands
        mock_precommit.return_value = "ruff check output"
        mock_test.return_value = "pytest output"

        precommit_result = await run_ruff_checks(target_path=target_path)
        test_result = await run_pytests(target_path=target_path, session_id=session_id)

        assert precommit_result == "ruff check output"
        assert test_result == "pytest output"

        assert mock_precommit.call_count == 1
        mock_test.assert_called_once()

    async def test_precommit_failure_stops_test(self, mock_run_precommit):
        target_path = Path("/test/path")
        mock_precommit = mock_run_precommit
        mock_precommit.side_effect = Exception("ruff check failed")

        with pytest.raises(Exception, match="ruff check failed"):
            await run_ruff_checks(target_path=target_path)
