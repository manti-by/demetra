from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.opencode import (
    PLAN_HAS_QUESTIONS,
    PLAN_IS_READY_STRING,
    opencode_build_agent,
    opencode_plan_agent,
    opencode_resolve_agent,
    run_opencode_agent,
)
from demetra.settings import OPENCODE


class TestOpencodeService:
    @pytest.fixture
    def mock_run_opencode_agent(self):
        with patch("demetra.services.opencode.run_opencode_agent", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_run_command_and_opencode_config(self):
        with (
            patch("demetra.services.opencode.run_command", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.opencode.OPENCODE", {"path": Path("/bin/opencode"), "model": "test-model"}),
        ):
            yield mock_run

    @pytest.mark.asyncio
    async def test_plan_agent_calls_run_opencode_agent(self, mock_run_opencode_agent):

        mock_run_opencode_agent.return_value = "plan result"
        result = await opencode_plan_agent(Path("/test/path"), "do something", task_title="do something")

        expected_task = (
            "do something"
            "\nIMPORTANT:"
            "\n- If you have some question about implementation, just print in the end `Please check my questions above.`"
            "\n- If there are no questions, just print in the end `Ready to proceed to build.`"
        )
        mock_run_opencode_agent.assert_called_once_with(
            target_path=Path("/test/path"),
            task=expected_task,
            task_title="do something",
            model=OPENCODE["plan_model"],
            agent="plan-agent",
            env=None,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_build_agent_modifies_task_with_instructions(self, mock_run_opencode_agent):

        mock_run_opencode_agent.return_value = "build result"
        await opencode_build_agent(Path("/test/path"), "implement feature", session_id="session-123")

        mock_run_opencode_agent.assert_called_once()
        call_kwargs = mock_run_opencode_agent.call_args.kwargs
        task = call_kwargs.get("task")
        assert task is not None
        assert "DO NOT commit or push any changes" in task
        assert "implement feature" in task

    @pytest.mark.asyncio
    async def test_run_opencode_agent_uses_correct_command(self, mock_run_command_and_opencode_config):

        mock_run_command_and_opencode_config.return_value = "output"
        await run_opencode_agent(
            Path("/test"), "task", model="opencode/minimax-m2.5-free", agent="plan", session_id="session-123"
        )

        call_args = mock_run_command_and_opencode_config.call_args
        command = call_args.kwargs["command"]
        assert "/bin/opencode" in str(command[0])
        assert "--session" in command
        assert "session-123" in command
        assert "--model" in command
        assert "opencode/minimax-m2.5-free" in command
        assert "--agent" in command
        assert "plan" in command

    @pytest.mark.asyncio
    async def test_plan_constants_are_defined(self):

        assert PLAN_IS_READY_STRING == "Ready to proceed to build."
        assert PLAN_HAS_QUESTIONS == "Please check my questions above."

    @pytest.mark.asyncio
    async def test_resolve_agent_uses_resolve_model(self, mock_run_opencode_agent):

        mock_run_opencode_agent.return_value = "resolve result"
        result = await opencode_resolve_agent(Path("/test/path"), "answer these questions")

        mock_run_opencode_agent.assert_called_once_with(
            target_path=Path("/test/path"),
            task="answer these questions",
            task_title=None,
            model=OPENCODE["resolve_model"],
            agent="resolve-agent",
            env=None,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_resolve_agent_uses_new_session(self, mock_run_opencode_agent):

        mock_run_opencode_agent.return_value = "resolve result"
        await opencode_resolve_agent(Path("/test/path"), "answer these questions", task_title="resolve-title")

        call_kwargs = mock_run_opencode_agent.call_args.kwargs
        assert call_kwargs.get("session_id") is None
        assert call_kwargs.get("agent") == "resolve-agent"
