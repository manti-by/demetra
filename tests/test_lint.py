from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.lint import run_ruff_checks


@pytest.mark.asyncio
async def test_ruff_checks_success():
    """Test successful ruff check execution."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with patch("demetra.services.lint.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (0, "ruff check output", "")

        result = await run_ruff_checks(target_path=target_path, session_id=session_id)

        assert mock_run.call_count == 1
        call = mock_run.call_args
        assert call[1]["command"] == ["uv", "run", "--active", "ruff", "check", "--quiet"]
        assert call[1]["target_path"] == target_path
        assert result == (0, "ruff check output", "")


@pytest.mark.asyncio
async def test_ruff_checks_failure():
    """Test ruff check when command fails."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with patch("demetra.services.lint.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = Exception("ruff check failed")

        with pytest.raises(Exception, match="ruff check failed"):
            await run_ruff_checks(target_path=target_path, session_id=session_id)

        assert mock_run.call_count == 1


@pytest.mark.asyncio
async def test_ruff_checks_no_session():
    """Test ruff check without session ID."""
    target_path = Path("/test/path")
    session_id = None

    with patch("demetra.services.lint.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (0, "ruff check output", "")

        result = await run_ruff_checks(target_path=target_path, session_id=session_id)

        assert mock_run.call_count == 1
        assert result == (0, "ruff check output", "")
