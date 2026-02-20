from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.precommit import run_ruff_checks
from demetra.services.test import run_tests


@pytest.mark.asyncio
async def test_precommit_and_test_integration():
    """Test that precommit and test agents work together in sequence."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with (
        patch("demetra.services.precommit.run_command", new_callable=AsyncMock) as mock_precommit,
        patch("demetra.services.test.run_command", new_callable=AsyncMock) as mock_test,
    ):
        mock_precommit.return_value = "ruff check output"
        mock_test.return_value = "pytest output"

        precommit_result = await run_ruff_checks(target_path=target_path, session_id=session_id)
        test_result = await run_tests(target_path=target_path, session_id=session_id)

        assert precommit_result == "ruff check output"
        assert test_result == "pytest output"

        assert mock_precommit.call_count == 1
        mock_test.assert_called_once()


@pytest.mark.asyncio
async def test_precommit_failure_stops_test():
    """Test that if precommit fails, test agent is not called."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with patch("demetra.services.precommit.run_command", new_callable=AsyncMock) as mock_precommit:
        mock_precommit.side_effect = Exception("ruff check failed")

        with pytest.raises(Exception, match="ruff check failed"):
            await run_ruff_checks(target_path=target_path, session_id=session_id)
