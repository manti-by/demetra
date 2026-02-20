import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from demetra.services.test import test_agent


@pytest.mark.asyncio
async def test_test_agent_success():
    """Test successful test agent execution."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with patch("demetra.services.test.run_command", new_callable=AsyncMock) as mock_run:
        # Mock successful test execution
        mock_run.return_value = "pytest output"

        result = await test_agent(target_path=target_path, session_id=session_id)

        # Verify command was called
        mock_run.assert_called_once_with(command=["uv", "run", "pytest", "tests/"], target_path=target_path)

        assert result == "pytest output"


@pytest.mark.asyncio
async def test_test_agent_failure():
    """Test test agent when tests fail."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with patch("demetra.services.test.run_command", new_callable=AsyncMock) as mock_run:
        # Mock test failure
        mock_run.side_effect = Exception("pytest failed")

        with pytest.raises(RuntimeError, match="Tests failed: pytest failed"):
            await test_agent(target_path=target_path, session_id=session_id)


@pytest.mark.asyncio
async def test_test_agent_no_session():
    """Test test agent without session ID."""
    target_path = Path("/test/path")
    session_id = None

    with patch("demetra.services.test.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "pytest output"

        result = await test_agent(target_path=target_path, session_id=session_id)

        mock_run.assert_called_once_with(command=["uv", "run", "pytest", "tests/"], target_path=target_path)
        assert result == "pytest output"
