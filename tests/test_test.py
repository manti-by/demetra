from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.test import run_pytests


@pytest.mark.asyncio
async def test_test_agent_success():
    """Test successful test agent execution."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with patch("demetra.services.test.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (0, "pytest output", "")

        result = await run_pytests(target_path=target_path, session_id=session_id)

        mock_run.assert_called_once_with(
            command=["uv", "run", "pytest", "--lf", "--quiet", "--color=no"], target_path=target_path
        )

        assert result == (0, "pytest output", "")


@pytest.mark.asyncio
async def test_test_agent_failure():
    """Test test agent when tests fail."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with patch("demetra.services.test.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = Exception("pytest failed")

        with pytest.raises(Exception, match="pytest failed"):
            await run_pytests(target_path=target_path, session_id=session_id)


@pytest.mark.asyncio
async def test_test_agent_no_session():
    """Test test agent without session ID."""
    target_path = Path("/test/path")
    session_id = None

    with patch("demetra.services.test.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (0, "pytest output", "")

        result = await run_pytests(target_path=target_path, session_id=session_id)

        mock_run.assert_called_once_with(
            command=["uv", "run", "pytest", "--lf", "--quiet", "--color=no"], target_path=target_path
        )
        assert result == (0, "pytest output", "")
