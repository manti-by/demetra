from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.precommit import run_ty_checks


@pytest.mark.asyncio
async def test_ty_checks_success():
    """Test successful ty check execution."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with patch("demetra.services.precommit.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "ty check output"

        result = await run_ty_checks(target_path=target_path, session_id=session_id)

        assert mock_run.call_count == 1
        call = mock_run.call_args
        assert call[1]["command"] == ["uvx", "ty", "check"]
        assert call[1]["target_path"] == target_path
        assert result == "ty check output"


@pytest.mark.asyncio
async def test_ty_checks_failure():
    """Test ty check when command fails."""
    target_path = Path("/test/path")
    session_id = "test-session"

    with patch("demetra.services.precommit.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = Exception("ty check failed")

        with pytest.raises(Exception, match="ty check failed"):
            await run_ty_checks(target_path=target_path, session_id=session_id)

        assert mock_run.call_count == 1


@pytest.mark.asyncio
async def test_ty_checks_no_session():
    """Test ty check without session ID."""
    target_path = Path("/test/path")
    session_id = None

    with patch("demetra.services.precommit.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "ty check output"

        result = await run_ty_checks(target_path=target_path, session_id=session_id)

        assert mock_run.call_count == 1
        assert result == "ty check output"
