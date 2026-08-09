from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.quality.test import run_pytests


class TestTestService:
    target_path = Path("/test/path")

    @pytest.fixture
    def mock_run(self):
        with patch("demetra.services.quality.test.run_command", new_callable=AsyncMock) as m:
            yield m

    @pytest.mark.asyncio
    async def test_agent_success(self, mock_run):
        mock_run.return_value = (0, "pytest output", "")
        result = await run_pytests(target_path=self.target_path, session_id="test-session")
        assert mock_run.call_count == 1
        assert result == (0, "pytest output", "")

    @pytest.mark.asyncio
    async def test_agent_failure(self, mock_run):
        mock_run.side_effect = Exception("pytest failed")
        with pytest.raises(Exception, match="pytest failed"):
            await run_pytests(target_path=self.target_path, session_id="test-session")

    @pytest.mark.asyncio
    async def test_agent_no_session(self, mock_run):
        mock_run.return_value = (0, "pytest output", "")
        result = await run_pytests(target_path=self.target_path, session_id=None)
        assert mock_run.call_count == 1
        assert result == (0, "pytest output", "")
