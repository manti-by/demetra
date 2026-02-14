from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


class TestOpencodeService:
    @pytest.mark.asyncio
    async def test_plan_agent_calls_run_opencode_agent(self):
        from demetra.services.opencode import plan_agent

        with patch("demetra.services.opencode.run_opencode_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "plan result"
            result = await plan_agent(Path("/test/path"), "do something")

        mock_run.assert_called_once_with(Path("/test/path"), "do something", repeat=False, agent="plan")
        assert result == "plan result"

    @pytest.mark.asyncio
    async def test_build_agent_modifies_task_with_instructions(self):
        from demetra.services.opencode import build_agent

        with patch("demetra.services.opencode.run_opencode_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "build result"
            await build_agent(Path("/test/path"), "implement feature")

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        args, kwargs = call_args
        task = args[1] if len(args) > 1 else kwargs.get("task")
        assert task is not None
        assert "DO NOT commit or push any changes" in task
        assert "implement feature" in task

    @pytest.mark.asyncio
    async def test_run_opencode_agent_uses_correct_command(self):
        from demetra.services.opencode import run_opencode_agent

        with (
            patch("demetra.services.opencode.run_command", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.opencode.OPENCODE_PATH", Path("/bin/opencode")),
            patch("demetra.services.opencode.OPENCODE_MODEL", "test-model"),
        ):
            mock_run.return_value = "output"
            await run_opencode_agent(Path("/test"), "task", agent="plan")

        call_args = mock_run.call_args
        command = call_args.kwargs["command"]
        assert "/bin/opencode" in str(command[0])
        assert "--model" in command
        assert "test-model" in command
        assert "--agent" in command
        assert "plan" in command

    @pytest.mark.asyncio
    async def test_run_opencode_agent_with_repeat_flag(self):
        from demetra.services.opencode import run_opencode_agent

        with (
            patch("demetra.services.opencode.run_command", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.opencode.OPENCODE_PATH", Path("/bin/opencode")),
            patch("demetra.services.opencode.OPENCODE_MODEL", "test-model"),
        ):
            mock_run.return_value = "output"
            await run_opencode_agent(Path("/test"), "task", repeat=True, agent="build")

        call_args = mock_run.call_args
        command = call_args.kwargs["command"]
        assert "--continue" in command
