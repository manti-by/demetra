from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.agents.cursor import cursor_review_agent, run_cursor_agent


class TestCursorService:
    @pytest.fixture
    def mock_run_command(self):
        with patch("demetra.services.agents.cursor.run_command", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_cursor_path(self):
        with patch("demetra.services.agents.cursor.CURSOR", {"path": Path("/bin/cursor")}):
            yield

    @pytest.fixture
    def mock_run_cursor_agent(self):
        with patch("demetra.services.agents.cursor.run_cursor_agent", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_review_agent_calls_run_cursor_agent(self, mock_run_cursor_agent):
        mock_run_cursor_agent.return_value = "review output"
        result = await cursor_review_agent(Path("/test/path"))

        mock_run_cursor_agent.assert_called_once()
        assert result == "review output"

    @pytest.mark.asyncio
    async def test_review_agent_task_contains_instructions(self, mock_run_cursor_agent):
        mock_run_cursor_agent.return_value = ""
        await cursor_review_agent(Path("/test"))

        call_kwargs = mock_run_cursor_agent.call_args.kwargs
        task = call_kwargs["task"]
        assert "staged changes" in task
        assert "high-severity issues" in task

    @pytest.mark.asyncio
    async def test_run_cursor_agent_uses_correct_command(self, mock_run_command, mock_cursor_path):
        mock_run_command.return_value = "output"
        await run_cursor_agent(Path("/test"), "custom task", "session-123")

        call_args = mock_run_command.call_args
        command = call_args.kwargs["command"]
        assert str(command[0]).endswith("cursor")
        assert "--session" in command
        assert "session-123" in command
        assert "--plan" in command
        assert "--print" in command
        assert "--force" in command
