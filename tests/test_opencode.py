import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.library.models import SessionEnvironment, SessionExport, TokenUsage
from demetra.services.agents.opencode import (
    RESEARCH_HEADER_STRING,
    capture_agent_session,
    extract_research_report,
    get_opencode_session_id,
    get_opencode_session_length,
    get_opencode_session_tokens,
    opencode_build_agent,
    opencode_compact_session,
    opencode_merge_agent,
    opencode_plan_agent,
    opencode_rebase_agent,
    opencode_research_agent,
    opencode_resolve_agent,
    opencode_supports_compaction,
    opencode_validate_agent,
    reset_opencode_cli_state,
    run_opencode_agent,
)
from demetra.settings import OPENCODE


@pytest.fixture(autouse=True)
def _reset_opencode_cli_state():
    reset_opencode_cli_state()
    yield
    reset_opencode_cli_state()


class TestOpencodeService:
    @pytest.fixture
    def mock_run_opencode_agent(self):
        with patch("demetra.services.agents.opencode.run_opencode_agent", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_run_command_and_opencode_config(self):
        with (
            patch("demetra.services.agents.opencode.run_command", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.agents.opencode.OPENCODE", {"path": Path("/bin/opencode"), "model": "test-model"}),
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
            project_id=None,
            environment=None,
        )
        assert result == "plan result"

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
        # Task is delivered via stdin, not as a command-line argument.
        assert all(arg != "task" for arg in command)
        assert call_args.kwargs["input_text"] == "task"

    @pytest.mark.asyncio
    async def test_run_opencode_agent_passes_full_task_without_truncation(self, mock_run_command_and_opencode_config):
        mock_run_command_and_opencode_config.return_value = "output"
        long_task = "line with 'quotes' and\nnewlines\n" + "x" * 20000
        await run_opencode_agent(Path("/test"), long_task, model="m", agent="resolve-agent")

        call_args = mock_run_command_and_opencode_config.call_args.kwargs
        # The raw task arrives verbatim via stdin so quotes and newlines stay
        # untouched and no argument length limit can truncate it.
        assert call_args["input_text"] == long_task
        assert all(arg != long_task for arg in call_args["command"])

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
            project_id=None,
            environment=None,
        )
        assert result == "resolve result"


class TestRunOpencodeAgentLangSmithEnv:
    @pytest.fixture
    def mock_run_command_and_opencode_config(self):
        with (
            patch("demetra.services.agents.opencode.run_command", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.agents.opencode.OPENCODE", {"path": Path("/bin/opencode"), "model": "test-model"}),
        ):
            yield mock_run

    @pytest.mark.asyncio
    async def test_environment_is_the_only_env_argument(self, mock_run_command_and_opencode_config):
        mock_run_command_and_opencode_config.return_value = "output"
        await run_opencode_agent(Path("/test"), "task", model="m", agent="plan-agent")

        call_kwargs = mock_run_command_and_opencode_config.call_args.kwargs
        assert call_kwargs["environment"] is None
        assert "extra" not in call_kwargs
        assert "env" not in call_kwargs

    @pytest.mark.asyncio
    async def test_environment_carries_the_tracing_vars_to_the_subprocess(self, mock_run_command_and_opencode_config):
        environment = SessionEnvironment(
            project_environment={"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "key-1"},
            user_environment={},
        )
        mock_run_command_and_opencode_config.return_value = "output"
        await run_opencode_agent(Path("/test"), "task", model="m", agent="plan-agent", environment=environment)

        call_kwargs = mock_run_command_and_opencode_config.call_args.kwargs
        assert call_kwargs["environment"] is environment
        subprocess_env = environment.subprocess_env
        assert subprocess_env["LANGSMITH_TRACING"] == "true"
        assert subprocess_env["TRACE_TO_LANGSMITH"] == "true"
        assert subprocess_env["LANGSMITH_API_KEY"] == "key-1"


class TestOpencodeValidateAgent:
    @pytest.fixture
    def mock_run_opencode_agent(self):
        with patch("demetra.services.agents.opencode.run_opencode_agent", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_get_prompt(self):
        with patch("demetra.services.agents.opencode.get_prompt", new_callable=AsyncMock) as mock:
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
            project_id=None,
            environment=None,
        )
        assert result == "validate result"

    @pytest.mark.asyncio
    async def test_validate_agent_passes_environment(self, mock_run_opencode_agent, mock_get_prompt):
        mock_run_opencode_agent.return_value = "validate result"
        mock_get_prompt.return_value = "validate prompt body"
        environment = SessionEnvironment(project_environment={"KEY": "val"}, user_environment={})

        await opencode_validate_agent(
            Path("/test/path"), "build plan", task_title="validate-title", environment=environment
        )

        call_kwargs = mock_run_opencode_agent.call_args.kwargs
        assert call_kwargs.get("task_title") == "validate-title"
        assert call_kwargs.get("environment") is environment
        assert call_kwargs.get("agent") == "validate-agent"


class TestOpencodeSessionId:
    """No exact worktree-directory match should still return the most recently updated
    same-titled session as a fallback, instead of None. Returning None here leaves the
    session's session_id empty in the DB, which keeps it stuck as 'pending' forever and
    blocks the watcher's step reset on future runs."""

    @pytest.fixture
    def mock_get_opencode_sessions(self):
        with patch("demetra.services.agents.opencode.get_opencode_sessions", new_callable=AsyncMock) as m:
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


class TestOpencodeSessionLength:
    @pytest.fixture
    def mock_run_command_and_config(self):
        with (
            patch("demetra.services.agents.opencode.run_command_to_file", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.agents.opencode.run_command", new_callable=AsyncMock) as mock_version,
            patch("demetra.services.agents.opencode.OPENCODE", {"path": Path("/bin/opencode")}),
        ):
            mock_version.return_value = (0, "2.0.30", "")
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

    @pytest.mark.parametrize(
        ("exit_code", "stdout", "stderr"),
        [
            (1, "", "error"),
            (0, "not json", ""),
            (0, "{}", ""),
            (0, '{"info": {}}', ""),
        ],
        ids=["nonzero_exit", "invalid_json", "info_missing", "tokens_missing"],
    )
    @pytest.mark.asyncio
    async def test_returns_none_for_unusable_export(self, mock_run_command_and_config, exit_code, stdout, stderr):
        mock_run_command_and_config.return_value = (exit_code, stdout, stderr)
        result = await get_opencode_session_length(Path("/p"), "session-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_uses_v2_session_export_command(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (0, '{"info": {"tokens": {"input": 0}}}', "")
        await get_opencode_session_length(Path("/p"), "ses_abc123")
        command = mock_run_command_and_config.call_args.kwargs["command"]
        assert command == ["/bin/opencode", "session", "export", "ses_abc123"]

    @pytest.mark.asyncio
    async def test_uses_v1_export_command(self, mock_run_command_and_config):
        with patch("demetra.services.agents.opencode.run_command", new_callable=AsyncMock) as mock_version:
            mock_version.return_value = (0, "1.18.30", "")
            reset_opencode_cli_state()
            mock_run_command_and_config.return_value = (0, '{"info": {"tokens": {"input": 0}}}', "")
            await get_opencode_session_length(Path("/p"), "ses_abc123")
        command = mock_run_command_and_config.call_args.kwargs["command"]
        assert command == ["/bin/opencode", "export", "ses_abc123"]

    @pytest.mark.asyncio
    async def test_passes_target_path_and_environment(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (0, '{"info": {"tokens": {"input": 0}}}', "")
        environment = SessionEnvironment(project_environment={"KEY": "val"}, user_environment={})
        await get_opencode_session_length(Path("/custom/path"), "s-1", environment=environment)
        call_kwargs = mock_run_command_and_config.call_args.kwargs
        assert call_kwargs["target_path"] == Path("/custom/path")
        assert call_kwargs["environment"] is environment


class TestOpencodeSessionTokens:
    @pytest.fixture
    def mock_run_command_and_config(self):
        with (
            patch("demetra.services.agents.opencode.run_command_to_file", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.agents.opencode.run_command", new_callable=AsyncMock) as mock_version,
            patch("demetra.services.agents.opencode.OPENCODE", {"path": Path("/bin/opencode")}),
        ):
            mock_version.return_value = (0, "2.0.30", "")
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

    @pytest.mark.parametrize(
        "messages",
        [
            [{"info": {"role": "user"}}],
            None,
            [
                {"info": {"role": "user"}},
                {"info": {"role": "assistant"}},
                {"info": {"role": "assistant", "tokens": {"input": 0, "output": 0, "reasoning": 0}}},
            ],
        ],
        ids=["no_assistant_messages", "messages_missing", "last_assistant_has_no_tokens"],
    )
    @pytest.mark.asyncio
    async def test_context_is_none_without_a_token_bearing_assistant_message(
        self, mock_run_command_and_config, messages
    ):
        payload = {"info": {"tokens": {"input": 100, "output": 50, "reasoning": 10}}}
        if messages is not None:
            payload["messages"] = messages
        mock_run_command_and_config.return_value = (0, json.dumps(payload), "")

        result = await get_opencode_session_tokens(Path("/p"), "session-1")

        assert result is not None
        assert result.input == 100
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
            patch("demetra.services.agents.opencode.run_command", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.agents.opencode.OPENCODE", {"path": Path("/bin/opencode")}),
        ):
            yield mock_run

    @pytest.mark.asyncio
    async def test_invokes_run_with_compact_command(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (0, "ok", "")
        exit_code, stdout, _stderr = await opencode_compact_session(Path("/p"), "ses_abc123")
        assert exit_code == 0
        assert stdout == "ok"
        command = mock_run_command_and_config.call_args.kwargs["command"]
        assert command == ["/bin/opencode", "run", "--session", "ses_abc123", "--command", "compact"]

    @pytest.mark.asyncio
    async def test_returns_error_when_compaction_unsupported(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (0, "2.0.30", "")
        exit_code, stdout, stderr = await opencode_compact_session(Path("/p"), "ses_abc123")
        assert exit_code != 0
        assert stdout == ""
        assert "not supported" in stderr
        assert mock_run_command_and_config.await_count == 1

    @pytest.mark.asyncio
    async def test_forwards_target_path_and_environment(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (0, "", "")
        environment = SessionEnvironment(project_environment={"KEY": "val"}, user_environment={})
        await opencode_compact_session(Path("/custom/path"), "s-1", environment=environment)
        call_kwargs = mock_run_command_and_config.call_args.kwargs
        assert call_kwargs["target_path"] == Path("/custom/path")
        assert call_kwargs["environment"] is environment

    @pytest.mark.asyncio
    async def test_disables_stdio_by_default(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (0, "", "")
        await opencode_compact_session(Path("/p"), "s-1")
        call_kwargs = mock_run_command_and_config.call_args.kwargs
        # opencode_compact_session uses disable_stdio=False
        assert call_kwargs.get("disable_stdio") is False


class TestOpencodeSupportsCompaction:
    @pytest.fixture
    def mock_major_version(self):
        with patch(
            "demetra.services.agents.opencode.get_opencode_major_version",
            new_callable=AsyncMock,
        ) as mock:
            yield mock

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("major", "expected"),
        [
            (None, True),
            (1, True),
            (2, False),
            (3, False),
        ],
    )
    async def test_major_version_decides_support(self, mock_major_version, major, expected):
        mock_major_version.return_value = major

        assert await opencode_supports_compaction(Path("/p")) is expected


class TestCaptureAgentSession:
    @pytest.fixture
    def mock_get_session_id(self):
        with patch(
            "demetra.services.agents.opencode.get_opencode_session_id",
            new_callable=AsyncMock,
        ) as mock:
            yield mock

    @pytest.fixture
    def mock_get_export(self):
        with patch(
            "demetra.services.agents.opencode.get_opencode_session_export",
            new_callable=AsyncMock,
        ) as mock:
            yield mock

    @pytest.fixture
    def mock_record_invocation(self):
        with patch(
            "demetra.services.agents.opencode.record_agent_invocation",
            new_callable=AsyncMock,
        ) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_records_invocation_from_export(self, mock_get_session_id, mock_get_export, mock_record_invocation):
        mock_get_export.return_value = SessionExport(
            tokens=TokenUsage(input=1000, output=500),
            agent="build",
            model="provider/model",
            cost=0.5,
            outcome="completed",
        )
        mock_record_invocation.return_value = "history"

        result = await capture_agent_session(task_id="TASK-1", step="build", target_path=Path("/p"), session_id="ses_1")

        assert result == "history"
        mock_get_session_id.assert_not_called()
        mock_record_invocation.assert_awaited_once_with(
            task_id="TASK-1",
            step="build",
            session_id="ses_1",
            usage=TokenUsage(input=1000, output=500),
            agent="build",
            model="provider/model",
            cost=0.5,
            outcome="completed",
            fork_of=None,
            is_primary=False,
        )

    @pytest.mark.asyncio
    async def test_resolves_session_by_title_when_absent(
        self, mock_get_session_id, mock_get_export, mock_record_invocation
    ):
        mock_get_session_id.return_value = "ses_resolved"
        mock_get_export.return_value = None
        mock_record_invocation.return_value = "history"

        await capture_agent_session(task_id="TASK-1", step="plan", target_path=Path("/p"), task_title="TASK-1 plan")

        mock_get_session_id.assert_awaited_once_with(
            target_path=Path("/p"),
            task_title="TASK-1 plan",
            environment=None,
            include_forks=False,
        )
        assert mock_record_invocation.call_args.kwargs["session_id"] == "ses_resolved"
        assert mock_record_invocation.call_args.kwargs["usage"] is None

    @pytest.mark.asyncio
    async def test_resolves_fork_by_title_including_forks(
        self, mock_get_session_id, mock_get_export, mock_record_invocation
    ):
        mock_get_session_id.return_value = "ses_fork"
        mock_get_export.return_value = SessionExport(tokens=TokenUsage(input=100))
        mock_record_invocation.return_value = "history"

        await capture_agent_session(
            task_id="TASK-1",
            step="build",
            target_path=Path("/p"),
            task_title="TASK-1 build",
            session_id="ses_parent",
            forked=True,
            is_primary=True,
        )

        assert mock_get_session_id.call_args.kwargs["include_forks"] is True
        assert mock_record_invocation.call_args.kwargs["fork_of"] == "ses_parent"
        assert mock_record_invocation.call_args.kwargs["is_primary"] is True

    @pytest.mark.asyncio
    async def test_skips_without_task_id(self, mock_get_session_id, mock_get_export, mock_record_invocation):
        result = await capture_agent_session(task_id=None, step="build", target_path=Path("/p"), session_id="ses_1")

        assert result is None
        mock_get_session_id.assert_not_called()
        mock_get_export.assert_not_called()
        mock_record_invocation.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_without_title_when_unresolved(
        self, mock_get_session_id, mock_get_export, mock_record_invocation
    ):
        result = await capture_agent_session(task_id="TASK-1", step="build", target_path=Path("/p"))

        assert result is None
        mock_get_session_id.assert_not_called()
        mock_get_export.assert_not_called()
        mock_record_invocation.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_session_cannot_be_resolved(
        self, mock_get_session_id, mock_get_export, mock_record_invocation
    ):
        mock_get_session_id.return_value = None

        result = await capture_agent_session(
            task_id="TASK-1", step="build", target_path=Path("/p"), task_title="TASK-1 build"
        )

        assert result is None
        mock_get_export.assert_not_called()
        mock_record_invocation.assert_not_called()

    @pytest.mark.asyncio
    async def test_swallows_persistence_errors(self, mock_get_session_id, mock_get_export, mock_record_invocation):
        from sqlalchemy.exc import SQLAlchemyError

        mock_get_export.return_value = SessionExport(tokens=TokenUsage(input=100))
        mock_record_invocation.side_effect = SQLAlchemyError("boom")

        result = await capture_agent_session(task_id="TASK-1", step="build", target_path=Path("/p"), session_id="ses_1")

        assert result is None


class TestOpencodeEnvLayers:
    """The opencode agent wrappers resolve their model from the user env before
    calling run_opencode_agent, falling back to the settings default."""

    @pytest.fixture
    def mock_run_opencode_agent(self):
        with patch("demetra.services.agents.opencode.run_opencode_agent", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_plan_agent_uses_user_env_model_override(self, mock_run_opencode_agent):
        environment = SessionEnvironment(
            project_environment={}, user_environment={"OPENCODE_PLAN_MODEL": "user/env-plan-model"}
        )

        await opencode_plan_agent(Path("/test/path"), "task", environment=environment)

        call_kwargs = mock_run_opencode_agent.call_args.kwargs
        assert call_kwargs["model"] == "user/env-plan-model"
        assert call_kwargs["environment"] is environment

    @pytest.mark.asyncio
    async def test_plan_agent_falls_back_to_settings_model(self, mock_run_opencode_agent):
        await opencode_plan_agent(Path("/test/path"), "task")

        call_kwargs = mock_run_opencode_agent.call_args.kwargs
        assert call_kwargs["model"] == OPENCODE["plan_model"]

    @pytest.mark.asyncio
    async def test_build_agent_uses_user_env_model_override(self, mock_run_opencode_agent):
        environment = SessionEnvironment(
            project_environment={}, user_environment={"OPENCODE_BUILD_MODEL": "user/env-build-model"}
        )

        await opencode_build_agent(Path("/test/path"), "task", environment=environment)

        call_kwargs = mock_run_opencode_agent.call_args.kwargs
        assert call_kwargs["model"] == "user/env-build-model"
        assert call_kwargs["environment"] is environment

    @pytest.mark.asyncio
    async def test_validate_agent_uses_user_env_model_override(self, mock_run_opencode_agent):
        environment = SessionEnvironment(
            project_environment={}, user_environment={"OPENCODE_VALIDATE_MODEL": "user/env-validate-model"}
        )

        await opencode_validate_agent(Path("/test/path"), "build plan", environment=environment)

        call_kwargs = mock_run_opencode_agent.call_args.kwargs
        assert call_kwargs["model"] == "user/env-validate-model"
        assert call_kwargs["environment"] is environment

    @pytest.mark.asyncio
    async def test_resolve_agent_uses_user_env_model_override(self, mock_run_opencode_agent):
        environment = SessionEnvironment(
            project_environment={}, user_environment={"OPENCODE_RESOLVE_MODEL": "user/env-resolve-model"}
        )

        await opencode_resolve_agent(Path("/test/path"), "task", environment=environment)

        call_kwargs = mock_run_opencode_agent.call_args.kwargs
        assert call_kwargs["model"] == "user/env-resolve-model"
        assert call_kwargs["environment"] is environment

    @pytest.mark.asyncio
    async def test_merge_agent_uses_user_env_build_model_override(self, mock_run_opencode_agent):
        environment = SessionEnvironment(
            project_environment={}, user_environment={"OPENCODE_BUILD_MODEL": "user/env-merge-model"}
        )

        await opencode_merge_agent(Path("/test/path"), "task", environment=environment)

        call_kwargs = mock_run_opencode_agent.call_args.kwargs
        assert call_kwargs["model"] == "user/env-merge-model"
        assert call_kwargs["environment"] is environment
        assert call_kwargs["agent"] == "merge-agent"

    @pytest.mark.asyncio
    async def test_rebase_agent_uses_user_env_build_model_override(self, mock_run_opencode_agent):
        environment = SessionEnvironment(
            project_environment={}, user_environment={"OPENCODE_BUILD_MODEL": "user/env-rebase-model"}
        )

        await opencode_rebase_agent(Path("/test/path"), "task", environment=environment)

        call_kwargs = mock_run_opencode_agent.call_args.kwargs
        assert call_kwargs["model"] == "user/env-rebase-model"
        assert call_kwargs["environment"] is environment
        assert call_kwargs["agent"] == "rebase-agent"


class TestOpencodeResearchAgent:
    @pytest.fixture
    def mock_run_opencode_agent(self):
        with patch("demetra.services.agents.opencode.run_opencode_agent", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_get_prompt(self):
        with patch("demetra.services.agents.opencode.get_prompt", new_callable=AsyncMock) as mock:
            mock.return_value = "research prompt body"
            yield mock

    @pytest.mark.asyncio
    async def test_research_agent_uses_research_model_and_agent(self, mock_run_opencode_agent, mock_get_prompt):
        mock_run_opencode_agent.return_value = (0, "output", "")

        result = await opencode_research_agent(Path("/test/path"), "investigate the bug")

        mock_get_prompt.assert_awaited_once_with(name="research_agent", task="investigate the bug")
        mock_run_opencode_agent.assert_called_once_with(
            target_path=Path("/test/path"),
            task="research prompt body",
            task_title=None,
            model=OPENCODE["research_model"],
            agent="research-agent",
            project_id=None,
            environment=None,
        )
        assert result == (0, "output", "")

    @pytest.mark.asyncio
    async def test_research_agent_respects_user_env_model_override(self, mock_run_opencode_agent, mock_get_prompt):
        environment = SessionEnvironment(
            project_environment={}, user_environment={"OPENCODE_RESEARCH_MODEL": "user/env-research-model"}
        )

        await opencode_research_agent(Path("/test/path"), "task", environment=environment)

        call_kwargs = mock_run_opencode_agent.call_args.kwargs
        assert call_kwargs["model"] == "user/env-research-model"
        assert call_kwargs["agent"] == "research-agent"
        assert call_kwargs["environment"] is environment

    @pytest.mark.asyncio
    async def test_research_agent_passes_environment(self, mock_run_opencode_agent, mock_get_prompt):
        environment = SessionEnvironment(project_environment={"API_KEY": "1"}, user_environment={})

        await opencode_research_agent(Path("/test/path"), "task", environment=environment)

        call_kwargs = mock_run_opencode_agent.call_args.kwargs
        assert call_kwargs["environment"] is environment

    @pytest.mark.asyncio
    async def test_extract_research_report_trims_leading_text(self):
        output = f"Preamble text\n{RESEARCH_HEADER_STRING}\nFindings here."

        assert await extract_research_report(research_output=output) == f"{RESEARCH_HEADER_STRING}\nFindings here."

    @pytest.mark.asyncio
    async def test_extract_research_report_keeps_output_without_header(self):
        assert await extract_research_report(research_output="raw output") == "raw output"
