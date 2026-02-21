from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


class TestOpencodeService:
    @pytest.mark.asyncio
    async def test_plan_agent_calls_run_opencode_agent(self):
        from demetra.services.opencode import plan_agent

        with patch("demetra.services.opencode.run_opencode_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "plan result"
            result = await plan_agent(
                Path("/test/path"), "do something", session_id="session-123", task_title="do something"
            )

        expected_task = (
            "do something"
            "\nIf you have some question about implementation, just print in the end `Please check my questions above.`"
            "\nIf there are no questions, just print in the end `Ready to proceed to build.`"
        )
        mock_run.assert_called_once_with(
            target_path=Path("/test/path"),
            task=expected_task,
            session_id="session-123",
            task_title="do something",
            agent="plan",
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_build_agent_modifies_task_with_instructions(self):
        from demetra.services.opencode import build_agent

        with patch("demetra.services.opencode.run_opencode_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "build result"
            await build_agent(Path("/test/path"), "implement feature", session_id="session-123")

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        task = call_kwargs.get("task")
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
            await run_opencode_agent(Path("/test"), "task", "plan", session_id="session-123")

        call_args = mock_run.call_args
        command = call_args.kwargs["command"]
        assert "/bin/opencode" in str(command[0])
        assert "--session" in command
        assert "session-123" in command
        assert "--model" in command
        assert "test-model" in command
        assert "--agent" in command
        assert "plan" in command

    @pytest.mark.asyncio
    async def test_extract_plan_creates_file_when_not_exists(self, tmp_path):
        from demetra.services.opencode import extract_plan

        plan_output = "some unnecessary text\n## Implementation Plan"
        assert await extract_plan(plan_output) == "## Implementation Plan"

        plan_output = "\nsome plan text\nReady to proceed to build.\n\n"
        assert await extract_plan(plan_output) == "some plan text"

    @pytest.mark.asyncio
    async def test_plan_constants_are_defined(self):
        from demetra.services.opencode import PLAN_HAS_QUESTIONS, PLAN_IS_READY_STRING

        assert PLAN_IS_READY_STRING == "Ready to proceed to build."
        assert PLAN_HAS_QUESTIONS == "Please check my questions above."

    @pytest.mark.asyncio
    async def test_extract_plan_strips_ready_string(self):
        from demetra.services.opencode import PLAN_IS_READY_STRING, extract_plan

        plan_output = f"some plan content\n{PLAN_IS_READY_STRING}\nmore text"
        result = await extract_plan(plan_output)
        assert result == "some plan content"

    @pytest.mark.asyncio
    async def test_extract_plan_strips_questions_string(self):
        from demetra.services.opencode import PLAN_HAS_QUESTIONS, extract_plan

        plan_output = f"some plan content\n{PLAN_HAS_QUESTIONS}\nmore text"
        result = await extract_plan(plan_output)
        assert result == "some plan content"
