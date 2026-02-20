import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from demetra.services.precommit import precommit_agent
from demetra.services.test import test_agent


@pytest.mark.asyncio
async def test_precommit_and_test_integration():
    """Test that precommit and test agents work together in sequence."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with (
        patch("demetra.services.precommit.run_command", new_callable=AsyncMock) as mock_precommit,
        patch("demetra.services.test.run_command", new_callable=AsyncMock) as mock_test,
    ):
        # Mock successful executions
        mock_precommit.side_effect = [
            "ty check output",  # ty check
            "pre-commit run output",  # pre-commit run
        ]
        mock_test.return_value = "pytest output"

        # Run precommit agent
        precommit_result = await precommit_agent(target_path=target_path, session_id=session_id)

        # Run test agent
        test_result = await test_agent(target_path=target_path, session_id=session_id)

        # Verify both agents succeeded
        assert "ty check passed" in precommit_result
        assert "pre-commit run passed" in precommit_result
        assert test_result == "pytest output"

        # Verify all commands were called
        assert mock_precommit.call_count == 2
        mock_test.assert_called_once()


@pytest.mark.asyncio
async def test_precommit_failure_stops_test():
    """Test that if precommit fails, test agent is not called."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with patch("demetra.services.precommit.run_command", new_callable=AsyncMock) as mock_precommit:
        # Mock precommit failure
        mock_precommit.side_effect = Exception("ty check failed")

        # Precommit should fail
        with pytest.raises(RuntimeError, match="ty check failed"):
            await precommit_agent(target_path=target_path, session_id=session_id)
