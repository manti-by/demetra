import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.opencode import (
    PLAN_HAS_QUESTIONS,
    PLAN_IS_READY_STRING,
    get_opencode_session_id,
    get_opencode_session_length,
    get_opencode_session_tokens,
    opencode_build_agent,
    opencode_compact_session,
    opencode_plan_agent,
    opencode_resolve_agent,
    opencode_validate_agent,
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
            "\n- Do NOT use markdown tables in the implementation plan. Use lists or paragraphs instead."
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


class TestOpencodeValidateAgent:
    @pytest.fixture
    def mock_run_opencode_agent(self):
        with patch("demetra.services.opencode.run_opencode_agent", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_get_prompt(self):
        with patch("demetra.services.opencode.get_prompt", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_validate_agent_uses_validate_model_and_prompt(self, mock_run_opencode_agent, mock_get_prompt):
        mock_run_opencode_agent.return_value = "validate result"
        mock_get_prompt.return_value = "validate prompt body"

        result = await opencode_validate_agent(Path("/test/path"), "build plan")

        mock_get_prompt.assert_awaited_once_with(name="validate_agent")
        mock_run_opencode_agent.assert_called_once_with(
            target_path=Path("/test/path"),
            task="validate prompt body\n\nBuild Plan:\nbuild plan",
            task_title=None,
            model=OPENCODE["validate_model"],
            agent="validate-agent",
            env=None,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_validate_agent_passes_env(self, mock_run_opencode_agent, mock_get_prompt):
        mock_run_opencode_agent.return_value = "validate result"
        mock_get_prompt.return_value = "validate prompt body"

        await opencode_validate_agent(Path("/test/path"), "build plan", task_title="validate-title", env={"KEY": "val"})

        call_kwargs = mock_run_opencode_agent.call_args.kwargs
        assert call_kwargs.get("task_title") == "validate-title"
        assert call_kwargs.get("env") == {"KEY": "val"}
        assert call_kwargs.get("agent") == "validate-agent"


class TestOpencodeSessionId:
    """No exact worktree-directory match should still return the most recently updated
    same-titled session as a fallback, instead of None. Returning None here leaves the
    session's session_id empty in the DB, which keeps it stuck as 'pending' forever and
    blocks the watcher's step reset on future runs."""

    @pytest.fixture
    def mock_get_opencode_sessions(self):
        with patch("demetra.services.opencode.get_opencode_sessions", new_callable=AsyncMock) as m:
            yield m

    @pytest.mark.asyncio
    async def test_returns_exact_directory_match(self, mock_get_opencode_sessions):
        mock_get_opencode_sessions.return_value = [
            {"id": "ses-other-dir", "title": "MNT-128", "directory": "/other/path", "updated": 2},
            {"id": "ses-exact", "title": "MNT-128", "directory": "/test/path", "updated": 1},
        ]

        result = await get_opencode_session_id(Path("/test/path"), "MNT-128")

        assert result == "ses-exact"

    @pytest.mark.asyncio
    async def test_returns_fallback_when_no_directory_matches(self, mock_get_opencode_sessions):
        mock_get_opencode_sessions.return_value = [
            {"id": "ses-newer", "title": "MNT-128", "directory": "/other/path", "updated": 2},
            {"id": "ses-older", "title": "MNT-128", "directory": "/another/path", "updated": 1},
        ]

        result = await get_opencode_session_id(Path("/test/path"), "MNT-128")

        assert result == "ses-newer"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_matching_titles(self, mock_get_opencode_sessions):
        mock_get_opencode_sessions.return_value = [
            {"id": "ses-other", "title": "MNT-999", "directory": "/test/path", "updated": 1},
        ]

        result = await get_opencode_session_id(Path("/test/path"), "MNT-128")

        assert result is None


class TestOpencodeSessionLength:
    @pytest.fixture
    def mock_run_command_and_config(self):
        with (
            patch("demetra.services.opencode.run_command_to_file", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.opencode.OPENCODE", {"path": Path("/bin/opencode")}),
        ):
            yield mock_run

    @pytest.mark.asyncio
    async def test_sums_all_token_fields(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            '{"info": {"tokens": {"input": 10, "output": 5, "reasoning": 1, "cache": {"read": 100, "write": 2}}}}',
            "",
        )
        result = await get_opencode_session_length(Path("/p"), "session-1")
        assert result == 118  # 10 + 5 + 1 + 100 + 2

    @pytest.mark.asyncio
    async def test_handles_missing_cache(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            '{"info": {"tokens": {"input": 20, "output": 3, "reasoning": 0}}}',
            "",
        )
        result = await get_opencode_session_length(Path("/p"), "session-1")
        assert result == 23

    @pytest.mark.asyncio
    async def test_returns_none_on_nonzero_exit(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (1, "", "error")
        result = await get_opencode_session_length(Path("/p"), "session-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_json(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (0, "not json", "")
        result = await get_opencode_session_length(Path("/p"), "session-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_info_missing(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (0, "{}", "")
        result = await get_opencode_session_length(Path("/p"), "session-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_tokens_missing(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (0, '{"info": {}}', "")
        result = await get_opencode_session_length(Path("/p"), "session-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_uses_correct_export_command(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (0, '{"info": {"tokens": {"input": 0}}}', "")
        await get_opencode_session_length(Path("/p"), "ses_abc123")
        command = mock_run_command_and_config.call_args.kwargs["command"]
        assert command == ["/bin/opencode", "export", "ses_abc123"]

    @pytest.mark.asyncio
    async def test_passes_target_path_and_env(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (0, '{"info": {"tokens": {"input": 0}}}', "")
        await get_opencode_session_length(Path("/custom/path"), "s-1", env={"KEY": "val"})
        call_kwargs = mock_run_command_and_config.call_args.kwargs
        assert call_kwargs["target_path"] == Path("/custom/path")
        assert call_kwargs["env"] == {"KEY": "val"}


class TestOpencodeSessionTokens:
    @pytest.fixture
    def mock_run_command_and_config(self):
        with (
            patch("demetra.services.opencode.run_command_to_file", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.opencode.OPENCODE", {"path": Path("/bin/opencode")}),
        ):
            yield mock_run

    @pytest.mark.asyncio
    async def test_extracts_context_from_last_assistant_message(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            json.dumps(
                {
                    "info": {"tokens": {"input": 100, "output": 50, "reasoning": 10}},
                    "messages": [
                        {"info": {"role": "user"}},
                        {
                            "info": {
                                "role": "assistant",
                                "tokens": {
                                    "input": 10,
                                    "output": 5,
                                    "reasoning": 2,
                                    "cache": {"read": 100, "write": 0},
                                },
                            }
                        },
                        {
                            "info": {
                                "role": "assistant",
                                "tokens": {
                                    "input": 20,
                                    "output": 8,
                                    "reasoning": 3,
                                    "cache": {"read": 200, "write": 0},
                                },
                            }
                        },
                    ],
                }
            ),
            "",
        )
        result = await get_opencode_session_tokens(Path("/p"), "session-1")
        assert result is not None
        assert result.context == 220  # 20 + 200

    @pytest.mark.asyncio
    async def test_context_is_none_when_no_assistant_messages(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            json.dumps(
                {
                    "info": {"tokens": {"input": 100, "output": 50, "reasoning": 10}},
                    "messages": [{"info": {"role": "user"}}],
                }
            ),
            "",
        )
        result = await get_opencode_session_tokens(Path("/p"), "session-1")
        assert result is not None
        assert result.context is None

    @pytest.mark.asyncio
    async def test_context_is_none_when_messages_missing(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            json.dumps({"info": {"tokens": {"input": 100, "output": 50, "reasoning": 10}}}),
            "",
        )
        result = await get_opencode_session_tokens(Path("/p"), "session-1")
        assert result is not None
        assert result.context is None

    @pytest.mark.asyncio
    async def test_context_is_none_when_last_assistant_has_no_tokens(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            json.dumps(
                {
                    "info": {"tokens": {"input": 100, "output": 50, "reasoning": 10}},
                    "messages": [
                        {"info": {"role": "user"}},
                        {"info": {"role": "assistant"}},
                        {"info": {"role": "assistant", "tokens": {"input": 0, "output": 0, "reasoning": 0}}},
                    ],
                }
            ),
            "",
        )
        result = await get_opencode_session_tokens(Path("/p"), "session-1")
        assert result is not None
        assert result.context is None

    @pytest.mark.asyncio
    async def test_existing_fields_unaffected_by_context_extraction(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            json.dumps(
                {
                    "info": {
                        "tokens": {"input": 100, "output": 50, "reasoning": 10, "cache": {"read": 30, "write": 2}}
                    },
                    "messages": [
                        {
                            "info": {
                                "role": "assistant",
                                "tokens": {
                                    "input": 20,
                                    "output": 8,
                                    "reasoning": 3,
                                    "cache": {"read": 200, "write": 0},
                                },
                            }
                        }
                    ],
                }
            ),
            "",
        )
        result = await get_opencode_session_tokens(Path("/p"), "session-1")
        assert result is not None
        assert result.input == 100
        assert result.output == 50
        assert result.reasoning == 10
        assert result.cache_read == 30
        assert result.cache_write == 2
        assert result.context == 220  # 20 + 200


class TestOpencodeCompactSession:
    @pytest.fixture
    def mock_run_command_and_config(self):
        with (
            patch("demetra.services.opencode.run_command", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.opencode.OPENCODE", {"path": Path("/bin/opencode")}),
        ):
            yield mock_run

    @pytest.mark.asyncio
    async def test_invokes_run_with_compact_command(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (0, "ok", "")
        exit_code, stdout, _stderr = await opencode_compact_session(Path("/p"), "ses_abc123")
        assert exit_code == 0
        assert stdout == "ok"
        command = mock_run_command_and_config.call_args.kwargs["command"]
        assert command == ["/bin/opencode", "run", "--session", "ses_abc123", "--dir", "/p", "/compact"]

    @pytest.mark.asyncio
    async def test_forwards_target_path_and_env(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (0, "", "")
        await opencode_compact_session(Path("/custom/path"), "s-1", env={"KEY": "val"})
        call_kwargs = mock_run_command_and_config.call_args.kwargs
        assert call_kwargs["target_path"] == Path("/custom/path")
        assert call_kwargs["env"] == {"KEY": "val"}

    @pytest.mark.asyncio
    async def test_disables_stdio_by_default(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (0, "", "")
        await opencode_compact_session(Path("/p"), "s-1")
        call_kwargs = mock_run_command_and_config.call_args.kwargs
        # opencode_compact_session uses disable_stdio=False
        assert call_kwargs.get("disable_stdio") is False
