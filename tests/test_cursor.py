from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


class TestCursorService:
    @pytest.mark.asyncio
    async def test_review_agent_calls_run_cursor_agent(self):
        from demetra.services.cursor import review_agent

        with patch("demetra.services.cursor.run_cursor_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "review output"
            result = await review_agent("session-123", Path("/test/path"))

        mock_run.assert_called_once()
        assert result == "review output"

    @pytest.mark.asyncio
    async def test_review_agent_task_contains_instructions(self):
        from demetra.services.cursor import review_agent

        with patch("demetra.services.cursor.run_cursor_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""
            await review_agent("session-123", Path("/test"))

        call_kwargs = mock_run.call_args.kwargs
        task = call_kwargs["task"]
        assert "Check git staged changes" in task
        assert "Review diff" in task

    @pytest.mark.asyncio
    async def test_run_cursor_agent_uses_correct_command(self):
        from demetra.services.cursor import run_cursor_agent

        with (
            patch("demetra.services.cursor.run_command", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.cursor.CURSOR_PATH", Path("/bin/cursor")),
        ):
            mock_run.return_value = "output"
            await run_cursor_agent("session-123", Path("/test"), "custom task")

        call_args = mock_run.call_args
        command = call_args.kwargs["command"]
        assert str(command[0]).endswith("cursor")
        assert "--resume" in command
        assert "session-123" in command
        assert "--plan" in command
        assert "--print" in command
        assert "--force" in command
