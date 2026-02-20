import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from demetra.services.precommit import precommit_agent


@pytest.mark.asyncio
async def test_precommit_agent_success():
    """Test successful pre-commit agent execution."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with patch("demetra.services.precommit.run_command", new_callable=AsyncMock) as mock_run:
        # Mock successful executions
        mock_run.side_effect = [
            "ty check output",  # First call for ty check
            "pre-commit run output",  # Second call for pre-commit run
        ]

        result = await precommit_agent(target_path=target_path, session_id=session_id)

        # Verify both commands were called
        assert mock_run.call_count == 2

        # Verify command arguments
        first_call = mock_run.call_args_list[0]
        assert first_call[1]["command"] == ["ty", "check"]
        assert first_call[1]["target_path"] == target_path

        second_call = mock_run.call_args_list[1]
        assert second_call[1]["command"] == ["pre-commit", "run"]
        assert second_call[1]["target_path"] == target_path

        # Verify result contains both outputs
        assert "ty check passed" in result
        assert "ty check output" in result
        assert "pre-commit run passed" in result
        assert "pre-commit run output" in result


@pytest.mark.asyncio
async def test_precommit_agent_ty_check_fails():
    """Test pre-commit agent when ty check fails."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with patch("demetra.services.precommit.run_command", new_callable=AsyncMock) as mock_run:
        # Mock ty check failure
        mock_run.side_effect = Exception("ty check failed")

        with pytest.raises(RuntimeError, match="ty check failed"):
            await precommit_agent(target_path=target_path, session_id=session_id)

        # Verify only ty check was called
        assert mock_run.call_count == 1


@pytest.mark.asyncio
async def test_precommit_agent_precommit_fails():
    """Test pre-commit agent when pre-commit run fails."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with patch("demetra.services.precommit.run_command", new_callable=AsyncMock) as mock_run:
        # Mock successful ty check but failed pre-commit
        mock_run.side_effect = [
            "ty check output",  # First call for ty check
            Exception("pre-commit run failed"),  # Second call for pre-commit run
        ]

        with pytest.raises(RuntimeError, match="pre-commit run failed"):
            await precommit_agent(target_path=target_path, session_id=session_id)

        # Verify both commands were called
        assert mock_run.call_count == 2


@pytest.mark.asyncio
async def test_precommit_agent_no_session():
    """Test pre-commit agent without session ID."""
    target_path = Path("/test/path")
    session_id = None

    with patch("demetra.services.precommit.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = ["ty check output", "pre-commit run output"]

        result = await precommit_agent(target_path=target_path, session_id=session_id)

        assert mock_run.call_count == 2
        assert "ty check passed" in result
