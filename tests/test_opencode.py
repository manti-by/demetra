import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.library.exceptions import (
    AgentBudgetRetryError,
    AgentCompactionError,
    AgentContextOverflowError,
    AgentNetworkError,
    AgentPermissionError,
    AgentProviderError,
    AgentQuotaError,
    AgentRateLimitError,
    BuildError,
    PlanError,
)
from demetra.library.models import ModelPrice, SessionEnvironment, SessionExport, SessionHistory, TokenUsage, ToolUsage
from demetra.services.agents.opencode import (
    RESEARCH_HEADER_STRING,
    agent_failure_error,
    capture_agent_session,
    classify_agent_error,
    extract_research_report,
    format_agent_error,
    get_opencode_session_export,
    get_opencode_session_id,
    get_opencode_session_length,
    get_opencode_session_tokens,
    get_opencode_sessions,
    is_network_error,
    opencode_build_agent,
    opencode_compact_session,
    opencode_merge_agent,
    opencode_plan_agent,
    opencode_rebase_agent,
    opencode_research_agent,
    opencode_resolve_agent,
    opencode_supports_compaction,
    opencode_supports_standalone,
    opencode_validate_agent,
    redact_provider_text,
    reset_opencode_cli_state,
    run_opencode_agent,
)
from demetra.settings import OPENCODE


@pytest.fixture(autouse=True)
def _reset_opencode_cli_state():
    reset_opencode_cli_state()
    yield
    reset_opencode_cli_state()


@pytest.fixture(autouse=True)
def _standalone_supported():
    with patch(
        "demetra.services.agents.opencode.opencode_supports_standalone", new_callable=AsyncMock, return_value=True
    ) as mock:
        yield mock


class TestOpencodeSupportsStandalone:
    @pytest.fixture
    def mock_run_command(self):
        with (
            patch("demetra.services.agents.opencode.run_command", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.agents.opencode.OPENCODE", {"path": Path("/bin/opencode"), "model": "test-model"}),
        ):
            yield mock_run

    @pytest.mark.asyncio
    async def test_true_when_help_lists_flag(self, mock_run_command):
        mock_run_command.return_value = (0, "Options:\n  --standalone  run without server\n  --model", "")

        assert await opencode_supports_standalone(target_path=Path("/test")) is True
        assert mock_run_command.await_args.kwargs["command"] == ["/bin/opencode", "run", "--help"]

    @pytest.mark.asyncio
    async def test_false_when_help_omits_flag(self, mock_run_command):
        mock_run_command.return_value = (0, "Options:\n  --model\n  --agent", "")

        assert await opencode_supports_standalone(target_path=Path("/test")) is False

    @pytest.mark.asyncio
    async def test_false_when_flag_is_only_a_prefix_of_another(self, mock_run_command):
        mock_run_command.return_value = (0, "  --standalone-mode", "")

        assert await opencode_supports_standalone(target_path=Path("/test")) is False

    @pytest.mark.asyncio
    async def test_result_is_cached_per_path(self, mock_run_command):
        mock_run_command.return_value = (0, "--standalone", "")

        await opencode_supports_standalone(target_path=Path("/test"))
        await opencode_supports_standalone(target_path=Path("/test"))

        mock_run_command.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_oserror_reports_unsupported_and_is_not_cached(self, mock_run_command):
        mock_run_command.side_effect = [OSError("spawn failed"), (0, "--standalone", "")]

        assert await opencode_supports_standalone(target_path=Path("/test")) is False
        assert await opencode_supports_standalone(target_path=Path("/test")) is True

    @pytest.mark.asyncio
    async def test_run_agent_still_runs_without_standalone_when_probe_hits_oserror(self, _standalone_supported):
        with (
            patch("demetra.services.agents.opencode.run_command", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.agents.opencode.OPENCODE", {"path": Path("/bin/opencode"), "model": "m"}),
            patch("demetra.services.agents.opencode.opencode_supports_standalone", new=opencode_supports_standalone),
        ):
            mock_run.side_effect = [OSError("spawn failed"), (0, "output", "")]
            result = await run_opencode_agent(Path("/test"), "task", model="m", agent="plan")

        assert result == (0, "output", "")
        agent_command = mock_run.await_args_list[1].kwargs["command"]
        assert agent_command == ["/bin/opencode", "run", "--model", "m", "--agent", "plan"]

    @pytest.mark.asyncio
    async def test_failed_probe_reports_unsupported_and_is_not_cached(self, mock_run_command):
        mock_run_command.side_effect = [(1, "", "boom"), (0, "--standalone", "")]

        assert await opencode_supports_standalone(target_path=Path("/test")) is False
        assert await opencode_supports_standalone(target_path=Path("/test")) is True


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
            retry_on_classified_failure=True,
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

        mock_run_command_and_opencode_config.return_value = (0, "output", "")
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
    async def test_run_opencode_agent_passes_standalone_when_supported(self, mock_run_command_and_opencode_config):
        mock_run_command_and_opencode_config.return_value = (0, "output", "")
        await run_opencode_agent(Path("/test"), "task", model="m", agent="plan")

        command = mock_run_command_and_opencode_config.call_args.kwargs["command"]
        assert command[:3] == ["/bin/opencode", "run", "--standalone"]

    @pytest.mark.asyncio
    async def test_run_opencode_agent_omits_standalone_when_unsupported(
        self, mock_run_command_and_opencode_config, _standalone_supported
    ):
        _standalone_supported.return_value = False
        mock_run_command_and_opencode_config.return_value = (0, "output", "")
        await run_opencode_agent(Path("/test"), "task", model="m", agent="plan")

        command = mock_run_command_and_opencode_config.call_args.kwargs["command"]
        assert command == ["/bin/opencode", "run", "--model", "m", "--agent", "plan"]

    @pytest.mark.asyncio
    async def test_run_opencode_agent_passes_full_task_without_truncation(self, mock_run_command_and_opencode_config):
        mock_run_command_and_opencode_config.return_value = (0, "output", "")
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
            retry_on_classified_failure=True,
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
        mock_run_command_and_opencode_config.return_value = (0, "output", "")
        await run_opencode_agent(Path("/test"), "task", model="m", agent="plan-agent")

        call_kwargs = mock_run_command_and_opencode_config.call_args.kwargs
        assert call_kwargs["environment"] is None
        assert "extra" not in call_kwargs
        assert "env" not in call_kwargs

    @pytest.mark.asyncio
    async def test_environment_carries_the_tracing_vars_to_the_subprocess(self, mock_run_command_and_opencode_config):
        with patch(
            "demetra.settings.LANGSMITH",
            {
                "tracing": True,
                "endpoint": "https://api.smith.langchain.com",
                "api_key": "key-1",
                "project": "Demetra",
            },
        ):
            environment = SessionEnvironment(project_environment={}, user_environment={})
            mock_run_command_and_opencode_config.return_value = (0, "output", "")
            await run_opencode_agent(Path("/test"), "task", model="m", agent="plan-agent", environment=environment)

            call_kwargs = mock_run_command_and_opencode_config.call_args.kwargs
            assert call_kwargs["environment"] is environment
            assert call_kwargs["forward_tracing"] is True
            subprocess_env = environment.subprocess_env
            assert subprocess_env["LANGSMITH_TRACING"] == "true"
            assert subprocess_env["TRACE_TO_LANGSMITH"] == "true"
            assert environment.tracing_env["LANGSMITH_API_KEY"] == "key-1"


class TestAgentNetworkRetry:
    """``run_opencode_agent`` retries a run whose output shows a transient
    network failure, backs off between attempts, and raises
    :class:`AgentNetworkError` once the budget is spent."""

    @pytest.fixture
    def network_retry_env(self):
        with (
            patch("demetra.services.agents.opencode.run_command", new_callable=AsyncMock) as mock_run_command,
            patch("demetra.services.agents.opencode.OPENCODE", {"path": Path("/bin/opencode"), "model": "test-model"}),
            patch("demetra.services.agents.opencode.MAX_AGENT_NETWORK_ATTEMPTS", 3),
            patch("demetra.services.agents.opencode.AGENT_NETWORK_BACKOFF_BASE", 1.0),
            patch("demetra.services.agents.opencode.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            yield mock_run_command, mock_sleep

    @pytest.mark.parametrize(
        "stdout, stderr",
        [
            ("", "Error: read ECONNRESET"),
            ('{"type": "error", "error": {"message": "fetch failed: socket hang up"}}', ""),
            ("", "connect ETIMEDOUT 1.2.3.4:443"),
            ("", "getaddrinfo EAI_AGAIN api.openai.com"),
        ],
    )
    def test_is_network_error_detects_transient_failures(self, stdout, stderr):
        assert is_network_error(stdout=stdout, stderr=stderr) is True

    @pytest.mark.parametrize(
        "stdout, stderr",
        [
            ("", ""),
            ("all tests passed", ""),
            ("", "error: econnreset while rendering a code sample"),
            ("", "Build agent failed (exit 1): Unexpected server error"),
            ("The ticket asks to handle read ECONNRESET from the provider", ""),
            ('{"type": "text", "text": "read ECONNRESET is handled in opencode.py"}', ""),
        ],
    )
    def test_is_network_error_ignores_other_output(self, stdout, stderr):
        assert is_network_error(stdout=stdout, stderr=stderr) is False

    @pytest.mark.asyncio
    async def test_returns_success_when_no_network_error(self, network_retry_env):
        mock_run_command, mock_sleep = network_retry_env
        mock_run_command.return_value = (0, "built", "")

        result = await run_opencode_agent(
            Path("/test"), "task", model="m", agent="build-agent", retry_on_classified_failure=True
        )

        assert result == (0, "built", "")
        mock_run_command.assert_awaited_once()
        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_retries_network_error_then_returns_success(self, network_retry_env):
        mock_run_command, mock_sleep = network_retry_env
        mock_run_command.side_effect = [(1, "", "read ECONNRESET"), (0, "built", "")]

        result = await run_opencode_agent(
            Path("/test"), "task", model="m", agent="build-agent", retry_on_classified_failure=True
        )

        assert result == (0, "built", "")
        assert mock_run_command.await_count == 2
        mock_sleep.assert_awaited_once_with(1.0)

    @pytest.mark.asyncio
    async def test_raises_after_budget_with_backoff(self, network_retry_env):
        mock_run_command, mock_sleep = network_retry_env
        mock_run_command.return_value = (1, "", "read ECONNRESET")

        with pytest.raises(AgentNetworkError) as exc_info:
            await run_opencode_agent(
                Path("/test"), "task", model="m", agent="build-agent", retry_on_classified_failure=True
            )

        assert mock_run_command.await_count == 3
        assert [call.args[0] for call in mock_sleep.await_args_list] == [1.0, 2.0]
        assert exc_info.value.agent == "build-agent"
        assert exc_info.value.stderr == "read ECONNRESET"
        assert "ECONNRESET" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_with_stdout_error_event_when_stderr_is_empty(self, network_retry_env):
        """opencode can report the failure as an NDJSON error event on stdout with
        empty stderr; the carried text must come from that event, not fall back to
        'unknown error'."""
        mock_run_command, _ = network_retry_env
        mock_run_command.return_value = (
            1,
            '{"type": "error", "error": {"message": "read ECONNRESET"}}',
            "",
        )

        with pytest.raises(AgentNetworkError) as exc_info:
            await run_opencode_agent(
                Path("/test"), "task", model="m", agent="build-agent", retry_on_classified_failure=True
            )

        assert exc_info.value.stderr == "read ECONNRESET"
        assert "ECONNRESET" in str(exc_info.value)
        assert "unknown error" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retry_resumes_the_forked_session_without_reforking(self, network_retry_env):
        mock_run_command, _ = network_retry_env
        mock_run_command.side_effect = [(1, "", "read ECONNRESET"), (0, "built", "")]

        with patch(
            "demetra.services.agents.opencode.get_opencode_session_id", new_callable=AsyncMock
        ) as mock_session_id:
            mock_session_id.return_value = "sess-fork"
            await run_opencode_agent(
                Path("/test"),
                "task",
                model="m",
                agent="build-agent",
                session_id="sess-plan",
                task_title="Title",
                fork=True,
                retry_on_classified_failure=True,
            )

        first_command = mock_run_command.await_args_list[0].kwargs["command"]
        second_command = mock_run_command.await_args_list[1].kwargs["command"]
        assert first_command == [
            "/bin/opencode",
            "run",
            "--standalone",
            "--model",
            "m",
            "--agent",
            "build-agent",
            "--session",
            "sess-plan",
            "--fork",
            "--title",
            "Title",
        ]
        assert second_command == [
            "/bin/opencode",
            "run",
            "--standalone",
            "--model",
            "m",
            "--agent",
            "build-agent",
            "--session",
            "sess-fork",
        ]
        mock_session_id.assert_awaited_once_with(
            target_path=Path("/test"), task_title="Title", environment=None, include_forks=True, forks_only=True
        )

    @pytest.mark.asyncio
    async def test_retry_stops_when_no_verified_fork_session_is_found(self, network_retry_env):
        mock_run_command, mock_sleep = network_retry_env
        mock_run_command.return_value = (1, "", "read ECONNRESET")

        with patch(
            "demetra.services.agents.opencode.get_opencode_session_id", new_callable=AsyncMock
        ) as mock_session_id:
            mock_session_id.return_value = None
            with pytest.raises(AgentNetworkError):
                await run_opencode_agent(
                    Path("/test"),
                    "task",
                    model="m",
                    agent="build-agent",
                    session_id="sess-plan",
                    task_title="Title",
                    fork=True,
                    retry_on_classified_failure=True,
                )

        mock_run_command.assert_awaited_once()
        mock_sleep.assert_not_awaited()
        command = mock_run_command.await_args.kwargs["command"]
        assert command.count("--fork") == 1
        assert "sess-plan" in command

    @pytest.mark.asyncio
    async def test_retry_resumes_the_session_created_by_the_failed_attempt(self, network_retry_env):
        mock_run_command, _ = network_retry_env
        mock_run_command.side_effect = [(1, "", "read ECONNRESET"), (0, "built", "")]

        with patch(
            "demetra.services.agents.opencode.get_opencode_session_id", new_callable=AsyncMock
        ) as mock_session_id:
            mock_session_id.return_value = "sess-first"
            await run_opencode_agent(
                Path("/test"),
                "task",
                model="m",
                agent="plan-agent",
                task_title="Title",
                retry_on_classified_failure=True,
            )

        second_command = mock_run_command.await_args_list[1].kwargs["command"]
        assert second_command == [
            "/bin/opencode",
            "run",
            "--standalone",
            "--model",
            "m",
            "--agent",
            "plan-agent",
            "--session",
            "sess-first",
        ]
        mock_session_id.assert_awaited_once_with(
            target_path=Path("/test"), task_title="Title", environment=None, include_forks=False, forks_only=False
        )

    @pytest.mark.asyncio
    async def test_does_not_retry_without_opt_in(self, network_retry_env):
        mock_run_command, mock_sleep = network_retry_env
        mock_run_command.return_value = (1, "", "read ECONNRESET")

        result = await run_opencode_agent(Path("/test"), "task", model="m", agent="merge-agent")

        assert result == (1, "", "read ECONNRESET")
        mock_run_command.assert_awaited_once()
        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_does_not_retry_non_network_failure(self, network_retry_env):
        mock_run_command, mock_sleep = network_retry_env
        mock_run_command.return_value = (1, "", "Unexpected server error")

        result = await run_opencode_agent(
            Path("/test"), "task", model="m", agent="build-agent", retry_on_classified_failure=True
        )

        assert result == (1, "", "Unexpected server error")
        mock_run_command.assert_awaited_once()
        mock_sleep.assert_not_awaited()


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
            retry_on_classified_failure=True,
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

    @pytest.mark.asyncio
    async def test_forks_only_never_matches_the_parent_session(self, mock_get_opencode_sessions):
        mock_get_opencode_sessions.return_value = [
            {"id": "ses-parent", "title": "MNT-128", "directory": "/test/path", "updated": 2},
            {"id": "ses-fork", "title": "MNT-128 (fork #1)", "directory": "/test/path", "updated": 1},
        ]

        result = await get_opencode_session_id(Path("/test/path"), "MNT-128", forks_only=True)

        assert result == "ses-fork"

    @pytest.mark.asyncio
    async def test_forks_only_returns_none_without_a_fork(self, mock_get_opencode_sessions):
        mock_get_opencode_sessions.return_value = [
            {"id": "ses-parent", "title": "MNT-128", "directory": "/test/path", "updated": 2},
        ]

        result = await get_opencode_session_id(Path("/test/path"), "MNT-128", forks_only=True)

        assert result is None


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


class TestExtractToolUsage:
    @pytest.fixture
    def mock_run_command_and_config(self):
        with (
            patch("demetra.services.agents.opencode.run_command_to_file", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.agents.opencode.run_command", new_callable=AsyncMock) as mock_version,
            patch("demetra.services.agents.opencode.OPENCODE", {"path": Path("/bin/opencode")}),
        ):
            mock_version.return_value = (0, "2.0.30", "")
            yield mock_run

    @staticmethod
    def _payload(messages: object) -> str:
        return json.dumps({"info": {"tokens": {"input": 1, "output": 1, "reasoning": 0}}, "messages": messages})

    @pytest.mark.asyncio
    async def test_counts_v2_content_parts(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            self._payload(
                [
                    {
                        "content": [
                            {"type": "text", "text": "working"},
                            {
                                "type": "tool",
                                "name": "bash",
                                "state": {"status": "completed"},
                                "time": {"created": 1000, "completed": 1100},
                            },
                            {
                                "type": "tool",
                                "name": "bash",
                                "state": {"status": "error"},
                                "time": {"created": 2000, "completed": 2050},
                            },
                            {
                                "type": "tool",
                                "name": "read",
                                "state": {"status": "running"},
                                "time": {"created": 3000},
                            },
                        ]
                    }
                ]
            ),
            "",
        )

        export = await get_opencode_session_export(Path("/p"), "session-1")

        assert export is not None
        bash = export.tool_usage["bash"]
        assert (bash.calls, bash.succeeded, bash.failed, bash.duration_ms) == (2, 1, 1, 150)
        read = export.tool_usage["read"]
        assert (read.calls, read.succeeded, read.failed, read.duration_ms) == (1, 0, 0, 0)

    @pytest.mark.asyncio
    async def test_counts_v1_parts_and_state_timing(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            self._payload(
                [
                    {
                        "info": {"role": "assistant"},
                        "parts": [
                            {
                                "type": "tool",
                                "tool": "grep",
                                "state": {"status": "completed", "time": {"start": 100, "end": 130}},
                            },
                            {
                                "type": "tool",
                                "tool": "grep",
                                "state": {"status": "error", "time": {"start": 200, "end": 210}},
                            },
                        ],
                    }
                ]
            ),
            "",
        )

        export = await get_opencode_session_export(Path("/p"), "session-1")

        assert export is not None
        grep = export.tool_usage["grep"]
        assert (grep.calls, grep.succeeded, grep.failed, grep.duration_ms) == (2, 1, 1, 40)

    @pytest.mark.asyncio
    async def test_watermark_excludes_inherited_parts(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            self._payload(
                [
                    {
                        "content": [
                            {
                                "type": "tool",
                                "name": "shell",
                                "state": {"status": "completed"},
                                "time": {"created": 1792922515390, "completed": 1792922515400},
                            },
                            {
                                "type": "tool",
                                "name": "shell",
                                "state": {"status": "completed"},
                                "time": {"created": 1792922527297, "completed": 1792922527307},
                            },
                        ]
                    }
                ]
            ),
            "",
        )

        export = await get_opencode_session_export(Path("/p"), "session-fork", invoked_at=1792922520000)

        assert export is not None
        assert export.tool_usage["shell"].calls == 1
        assert export.tool_usage["shell"].duration_ms == 10

    @pytest.mark.asyncio
    async def test_watermark_skips_parts_without_timing(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            self._payload([{"content": [{"type": "tool", "name": "bash", "state": {"status": "completed"}}]}]),
            "",
        )

        export = await get_opencode_session_export(Path("/p"), "session-1", invoked_at=1)

        assert export is not None
        assert export.tool_usage == {}

    @pytest.mark.asyncio
    async def test_counts_tools_invoked_by_code_mode_execute(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            self._payload(
                [
                    {
                        "content": [
                            {
                                "type": "tool",
                                "name": "execute",
                                "state": {
                                    "status": "completed",
                                    "metadata": {
                                        "toolCalls": [
                                            {"tool": "WI.wiki_search", "status": "completed"},
                                            {"tool": "Demetra.list_tables", "status": "error"},
                                        ]
                                    },
                                },
                                "time": {"created": 1000, "completed": 1100},
                            }
                        ]
                    }
                ]
            ),
            "",
        )

        export = await get_opencode_session_export(Path("/p"), "session-1")

        assert export is not None
        assert export.tool_usage["execute"].calls == 1
        wiki = export.tool_usage["WI.wiki_search"]
        assert (wiki.calls, wiki.succeeded, wiki.failed, wiki.duration_ms) == (1, 1, 0, 0)
        tables = export.tool_usage["Demetra.list_tables"]
        assert (tables.calls, tables.succeeded, tables.failed) == (1, 0, 1)

    @pytest.mark.asyncio
    async def test_counts_nested_tool_calls_from_event_stream_metadata(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            self._payload(
                [
                    {
                        "content": [
                            {
                                "type": "tool",
                                "name": "execute",
                                "state": {
                                    "status": "completed",
                                    "metadata": {
                                        "metadata": {"toolCalls": [{"tool": "WI.wiki_get_page", "status": "completed"}]}
                                    },
                                },
                            }
                        ]
                    }
                ]
            ),
            "",
        )

        export = await get_opencode_session_export(Path("/p"), "session-1")

        assert export is not None
        assert export.tool_usage["WI.wiki_get_page"].calls == 1

    @pytest.mark.asyncio
    async def test_code_mode_calls_follow_their_part_watermark(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            self._payload(
                [
                    {
                        "content": [
                            {
                                "type": "tool",
                                "name": "execute",
                                "state": {
                                    "status": "completed",
                                    "metadata": {"toolCalls": [{"tool": "WI.wiki_search", "status": "completed"}]},
                                },
                                "time": {"created": 1000, "completed": 1100},
                            }
                        ]
                    }
                ]
            ),
            "",
        )

        export = await get_opencode_session_export(Path("/p"), "session-1", invoked_at=2000)

        assert export is not None
        assert export.tool_usage == {}

    @pytest.mark.asyncio
    async def test_uses_ran_key_when_created_is_absent(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            self._payload(
                [
                    {
                        "content": [
                            {
                                "type": "tool",
                                "name": "edit",
                                "state": {"status": "completed"},
                                "time": {"ran": 100, "completed": 130},
                            }
                        ]
                    }
                ]
            ),
            "",
        )

        export = await get_opencode_session_export(Path("/p"), "session-1", invoked_at=50)

        assert export is not None
        assert export.tool_usage["edit"].calls == 1
        assert export.tool_usage["edit"].duration_ms == 30

    @pytest.mark.asyncio
    async def test_no_messages_yields_no_tool_usage(self, mock_run_command_and_config):
        mock_run_command_and_config.return_value = (
            0,
            self._payload([]),
            "",
        )

        export = await get_opencode_session_export(Path("/p"), "session-1")

        assert export is not None
        assert export.tool_usage == {}


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
        history = SessionHistory(
            id="history",
            session_id="ses_1",
            step="build",
            created_at="2026-01-01T00:00:00Z",
            kind="invocation",
        )
        mock_record_invocation.return_value = history

        result = await capture_agent_session(task_id="TASK-1", step="build", target_path=Path("/p"), session_id="ses_1")

        assert result is history
        mock_get_session_id.assert_not_called()
        mock_record_invocation.assert_awaited_once_with(
            task_id="TASK-1",
            step="build",
            session_id="ses_1",
            usage=TokenUsage(input=1000, output=500),
            agent="build",
            model="provider/model",
            cost=0.5,
            price=None,
            rate_card=None,
            outcome="completed",
            fork_of=None,
            is_primary=False,
            tool_usage={},
        )

    @pytest.mark.asyncio
    async def test_external_provider_cost_is_derived_from_the_rate_card(
        self, mock_get_session_id, mock_get_export, mock_record_invocation
    ):
        mock_get_export.return_value = SessionExport(
            tokens=TokenUsage(input=1_000_000, output=100_000),
            agent="build",
            model="deepseek/deepseek-v4-flash",
        )
        price = ModelPrice(provider="deepseek", source="test", input=0.3, output=1.2, cache_read=0.006)

        with patch(
            "demetra.services.agents.opencode.get_price", new_callable=AsyncMock, return_value=price
        ) as mock_get_price:
            await capture_agent_session(task_id="TASK-2", step="build", target_path=Path("/p"), session_id="ses_2")

        mock_get_price.assert_awaited_once_with(model="deepseek/deepseek-v4-flash")
        kwargs = mock_record_invocation.await_args.kwargs
        assert kwargs["cost"] is None
        assert kwargs["rate_card"] == price
        assert kwargs["price"] == {"input": 0.3, "output": 1.2, "cache_read": 0.006, "cache_write": 0.0}

    @pytest.mark.asyncio
    async def test_forwards_invocation_watermark_and_tool_usage(
        self, mock_get_session_id, mock_get_export, mock_record_invocation
    ):
        mock_get_export.return_value = SessionExport(
            tokens=TokenUsage(input=100),
            tool_usage={"bash": ToolUsage(name="bash", calls=2, succeeded=2, duration_ms=15)},
        )
        mock_record_invocation.return_value = SessionHistory(
            id="history",
            session_id="ses_1",
            step="build",
            created_at="2026-01-01T00:00:00Z",
            kind="invocation",
            tool_usage=[ToolUsage(name="bash", calls=2, succeeded=2, duration_ms=15)],
        )

        await capture_agent_session(
            task_id="TASK-1",
            step="build",
            target_path=Path("/p"),
            session_id="ses_1",
            invoked_at=4000,
        )

        assert mock_get_export.call_args.kwargs["invoked_at"] == 4000
        assert mock_record_invocation.call_args.kwargs["tool_usage"] == {
            "bash": ToolUsage(name="bash", calls=2, succeeded=2, duration_ms=15)
        }

    @pytest.mark.asyncio
    async def test_resolves_session_by_title_when_absent(
        self, mock_get_session_id, mock_get_export, mock_record_invocation
    ):
        mock_get_session_id.return_value = "ses_resolved"
        mock_get_export.return_value = None
        mock_record_invocation.return_value = None

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
        mock_record_invocation.return_value = None

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

    @pytest.mark.asyncio
    async def test_swallows_session_resolution_errors(
        self, mock_get_session_id, mock_get_export, mock_record_invocation
    ):
        mock_get_session_id.side_effect = ValueError("session list returned non-JSON")

        result = await capture_agent_session(
            task_id="TASK-1", step="build", target_path=Path("/p"), task_title="TASK-1 build"
        )

        assert result is None
        mock_get_export.assert_not_called()
        mock_record_invocation.assert_not_called()


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
            retry_on_classified_failure=True,
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


class TestEmptySessionId:
    @pytest.fixture
    def mock_run_command_and_opencode_config(self):
        with (
            patch("demetra.services.agents.opencode.run_command", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.agents.opencode.OPENCODE", {"path": Path("/bin/opencode"), "model": "m"}),
        ):
            yield mock_run

    @pytest.mark.asyncio
    async def test_empty_session_id_omits_session_and_fork(self, mock_run_command_and_opencode_config):
        mock_run_command_and_opencode_config.return_value = (0, "output", "")

        await run_opencode_agent(
            Path("/test"),
            "task",
            model="m",
            agent="build-agent",
            session_id="",
            task_title="Title",
            fork=True,
        )

        command = mock_run_command_and_opencode_config.await_args.kwargs["command"]
        assert "--session" not in command
        assert "--fork" not in command
        assert "--title" in command

    @pytest.mark.asyncio
    async def test_empty_session_id_omits_session_without_fork(self, mock_run_command_and_opencode_config):
        mock_run_command_and_opencode_config.return_value = (0, "output", "")

        await run_opencode_agent(Path("/test"), "task", model="m", agent="plan", session_id="")

        command = mock_run_command_and_opencode_config.await_args.kwargs["command"]
        assert "--session" not in command
        assert "" not in command

    @pytest.mark.asyncio
    @pytest.mark.parametrize("stdout", ["", "not json", '{"id": "ses_1"}'])
    async def test_get_opencode_sessions_tolerates_bad_output(self, mock_run_command_and_opencode_config, stdout):
        mock_run_command_and_opencode_config.return_value = (0, stdout, "")

        assert await get_opencode_sessions(Path("/test")) == []

    @pytest.mark.asyncio
    async def test_get_opencode_sessions_parses_valid_output(self, mock_run_command_and_opencode_config):
        sessions = [{"id": "ses_1", "title": "Title", "updated": 1, "directory": "/test"}]
        mock_run_command_and_opencode_config.return_value = (0, json.dumps(sessions), "")

        assert await get_opencode_sessions(Path("/test")) == sessions


class TestAgentFailureClassification:
    """Provider stderr maps onto typed errors, with specific signatures winning
    over broad ones and credentials stripped from every rendered text."""

    @pytest.fixture
    def failure_retry_env(self):
        with (
            patch("demetra.services.agents.opencode.run_command", new_callable=AsyncMock) as mock_run_command,
            patch("demetra.services.agents.opencode.OPENCODE", {"path": Path("/bin/opencode"), "model": "test-model"}),
            patch("demetra.services.agents.opencode.MAX_AGENT_NETWORK_ATTEMPTS", 5),
            patch("demetra.services.agents.opencode.MAX_AGENT_FAILURE_ATTEMPTS", 3),
            patch("demetra.services.agents.opencode.AGENT_NETWORK_BACKOFF_BASE", 1.0),
            patch("demetra.services.agents.opencode.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            yield mock_run_command, mock_sleep

    @pytest.mark.parametrize(
        "stderr, code, error_class, retryable",
        [
            ("Your workspace has reached its monthly spending limit of $30", "quota_exhausted", AgentQuotaError, False),
            (
                "This request requires more credits; reduce max_tokens and retry",
                "budget_retry",
                AgentBudgetRetryError,
                True,
            ),
            ("RATE_LIMIT_EXCEEDED: too many requests", "rate_limited", AgentRateLimitError, True),
            ("PERMISSION_DENIED: 403 Forbidden for model", "permission_denied", AgentPermissionError, False),
            (
                "CONTEXT_LENGTH exceeded: maximum context length is 8192",
                "context_overflow",
                AgentContextOverflowError,
                False,
            ),
            ("compaction unavailable in this OpenCode build", "compaction_unavailable", AgentCompactionError, False),
            ("read ECONNRESET while fetching", "network_error", AgentNetworkError, True),
            ("UnknownError: Unexpected server error (err_123)", "unknown_server_error", AgentProviderError, False),
        ],
    )
    def test_classifies_stderr_signatures(self, stderr, code, error_class, retryable):
        classification = classify_agent_error(stdout="", stderr=stderr)

        assert classification is not None
        assert classification.code == code
        assert classification.error_class is error_class
        assert classification.retryable is retryable

    def test_budget_rejection_wins_over_plain_credit_exhaustion(self):
        stderr = "insufficient credits for this request: reduce max_tokens and retry"

        classification = classify_agent_error(stdout="", stderr=stderr)

        assert classification is not None
        assert classification.code == "budget_retry"
        assert classification.error_class is AgentBudgetRetryError

    def test_structured_type_and_retry_after_ms_are_read(self):
        stdout = json.dumps(
            {
                "type": "error",
                "error": {
                    "type": "InsufficientCredits",
                    "message": "This request requires more credits",
                    "metadata": {"limit_source": "in-flight"},
                    "retryAfterMs": 250,
                },
            }
        )

        classification = classify_agent_error(stdout=stdout, stderr="")

        assert classification is not None
        assert classification.code == "budget_retry"
        assert classification.retry_after_ms == 250
        assert classification.retryable is True

    def test_structured_quota_without_in_flight_source_is_not_retryable(self):
        stdout = json.dumps(
            {
                "type": "error",
                "error": {"type": "InsufficientCredits", "message": "monthly spending limit reached"},
            }
        )

        classification = classify_agent_error(stdout=stdout, stderr="")

        assert classification is not None
        assert classification.code == "quota_exhausted"
        assert classification.retryable is False

    def test_structured_unknown_error_is_not_retried(self):
        stdout = json.dumps({"type": "error", "error": {"type": "UnknownError", "message": "Unexpected server error"}})

        classification = classify_agent_error(stdout=stdout, stderr="")

        assert classification is not None
        assert classification.code == "unknown_server_error"
        assert classification.error_class is AgentProviderError
        assert classification.retryable is False

    @pytest.mark.parametrize(
        "stdout, stderr",
        [
            ("", ""),
            ("", "Unexpected failure with no known signature"),
            ("", "error: econnreset while rendering a code sample"),
            ('{"type": "text", "text": "rate limit is handled in opencode.py"}', ""),
        ],
    )
    def test_unclassified_output_returns_none(self, stdout, stderr):
        assert classify_agent_error(stdout=stdout, stderr=stderr) is None

    def test_redacts_credential_urls_and_key_identifiers(self):
        text = "open https://openrouter.ai/keys/sk-or-v1-abcdef123456 with sk-proj-abcdefghijklmnop"

        redacted = redact_provider_text(text)

        assert "sk-or-v1-" not in redacted
        assert "sk-proj-abcdefghijklmnop" not in redacted
        assert "[redacted-url]" in redacted
        assert "[redacted-key]" in redacted

    def test_classified_error_carries_redacted_stderr_and_code(self):
        error = agent_failure_error(
            agent="plan-agent",
            exit_code=1,
            stdout="",
            stderr="insufficient credits; key sk-proj-abcdefghijklmnop",
            fallback=PlanError,
        )

        assert isinstance(error, AgentQuotaError)
        assert error.code == "quota_exhausted"
        assert "sk-proj-abcdefghijklmnop" not in error.stderr
        assert "[redacted-key]" in error.stderr
        assert "quota_exhausted" in str(error)

    def test_unclassified_error_uses_flat_fallback(self):
        error = agent_failure_error(
            agent="build-agent",
            exit_code=1,
            stdout="",
            stderr="some unclassified failure",
            fallback=BuildError,
        )

        assert type(error) is BuildError
        assert str(error) == "Build agent failed (exit 1): some unclassified failure"
        assert agent_failure_error(agent="build-agent", exit_code=1, stdout="", stderr="unclassified") is None

    def test_format_agent_error_redacts_provider_output(self):
        result = format_agent_error(
            exit_code=1,
            stdout="",
            stderr="failed with key sk-proj-abcdefghijklmnop at https://openrouter.ai/keys/sk-or-v1-abcdef123456",
        )

        assert "sk-proj-abcdefghijklmnop" not in result
        assert "sk-or-v1-abcdef123456" not in result

    @pytest.mark.asyncio
    async def test_retryable_class_exhausts_separate_budget_and_raises_mapped_error(self, failure_retry_env):
        mock_run_command, mock_sleep = failure_retry_env
        mock_run_command.return_value = (1, "", "RATE_LIMIT_EXCEEDED: too many requests")

        with pytest.raises(AgentRateLimitError) as exc_info:
            await run_opencode_agent(
                Path("/test"), "task", model="m", agent="plan-agent", retry_on_classified_failure=True
            )

        assert mock_run_command.await_count == 3
        assert [call.args[0] for call in mock_sleep.await_args_list] == [1.0, 2.0]
        assert exc_info.value.code == "rate_limited"
        assert exc_info.value.agent == "plan-agent"

    @pytest.mark.asyncio
    async def test_network_and_failure_budgets_are_independent(self, failure_retry_env):
        mock_run_command, mock_sleep = failure_retry_env
        mock_run_command.side_effect = [
            (1, "", "read ECONNRESET"),
            (1, "", "RATE_LIMIT_EXCEEDED: too many requests"),
            (1, "", "read ECONNRESET"),
            (1, "", "RATE_LIMIT_EXCEEDED: too many requests"),
            (1, "", "read ECONNRESET"),
        ]

        with (
            patch("demetra.services.agents.opencode.MAX_AGENT_NETWORK_ATTEMPTS", 3),
            pytest.raises(AgentNetworkError),
        ):
            await run_opencode_agent(
                Path("/test"), "task", model="m", agent="plan-agent", retry_on_classified_failure=True
            )

        assert mock_run_command.await_count == 5
        assert [call.args[0] for call in mock_sleep.await_args_list] == [1.0, 1.0, 2.0, 2.0]

    @pytest.mark.asyncio
    async def test_non_retryable_class_does_not_enter_retry_loop(self, failure_retry_env):
        mock_run_command, mock_sleep = failure_retry_env
        mock_run_command.return_value = (1, "", "UnknownError: Unexpected server error")

        result = await run_opencode_agent(
            Path("/test"), "task", model="m", agent="plan-agent", retry_on_classified_failure=True
        )

        assert result == (1, "", "UnknownError: Unexpected server error")
        mock_run_command.assert_awaited_once()
        mock_sleep.assert_not_awaited()

    def test_max_tokens_in_a_context_overflow_is_not_a_budget_rejection(self):
        stderr = "maximum context length exceeded; requested max_tokens=4096"

        classification = classify_agent_error(stdout="", stderr=stderr)

        assert classification is not None
        assert classification.code == "context_overflow"
        assert classification.error_class is AgentContextOverflowError
        assert classification.retryable is False

    def test_reducing_max_tokens_still_marks_a_budget_rejection(self):
        classification = classify_agent_error(stdout="", stderr="insufficient credits: reduce max_tokens and retry")

        assert classification is not None
        assert classification.code == "budget_retry"
        assert classification.retryable is True

    @pytest.mark.parametrize(
        "text, secret",
        [
            ("HTTP 403: Authorization: Bearer opaque-provider-credential", "opaque-provider-credential"),
            ("HTTP 401: Authorization: Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA=="),
            ('{"error": "bad", "api_key": "super-secret-value"}', "super-secret-value"),
            ("invalid token='literal-secret-value' for model", "literal-secret-value"),
            ("open https://user:password@provider.example.com/v1/models", "password@provider.example.com"),
        ],
    )
    def test_redacts_authorization_values_quoted_fields_and_url_userinfo(self, text, secret):
        assert secret not in redact_provider_text(text)

    def test_structured_unknown_error_with_network_evidence_is_retried(self):
        stdout = json.dumps({"type": "error", "error": {"type": "UnknownError", "message": "ECONNRESET"}})

        classification = classify_agent_error(stdout=stdout, stderr="")

        assert classification is not None
        assert classification.code == "network_error"
        assert classification.error_class is AgentNetworkError
        assert classification.retryable is True

    def test_structured_unknown_error_without_evidence_stays_a_provider_error(self):
        stdout = json.dumps({"type": "error", "error": {"type": "UnknownError", "message": "something odd"}})

        classification = classify_agent_error(stdout=stdout, stderr="")

        assert classification is not None
        assert classification.code == "unknown_server_error"
        assert classification.error_class is AgentProviderError
        assert classification.retryable is False

    @pytest.mark.asyncio
    async def test_unknown_error_with_network_evidence_retries_the_run(self, failure_retry_env):
        mock_run_command, _ = failure_retry_env
        stdout = json.dumps({"type": "error", "error": {"type": "UnknownError", "message": "ECONNRESET"}})
        mock_run_command.side_effect = [(1, stdout, ""), (0, "done", "")]

        result = await run_opencode_agent(
            Path("/test"), "task", model="m", agent="plan-agent", retry_on_classified_failure=True
        )

        assert result == (0, "done", "")
        assert mock_run_command.await_count == 2

    def test_unclassified_error_keeps_the_redacted_stdout_detail(self):
        error = agent_failure_error(
            agent="build-agent",
            exit_code=1,
            stdout="Requested model is unavailable with key sk-proj-abcdefghijklmnop",
            stderr="",
            fallback=BuildError,
        )

        assert "Requested model is unavailable" in str(error)
        assert "unknown error" not in str(error)
        assert "sk-proj-abcdefghijklmnop" not in str(error)

    @pytest.mark.asyncio
    async def test_retry_waits_for_the_provider_retry_after_delay(self, failure_retry_env):
        mock_run_command, mock_sleep = failure_retry_env
        stdout = json.dumps(
            {
                "type": "error",
                "error": {"type": "RateLimit", "message": "rate limit reached", "retryAfterMs": 5000},
            }
        )
        mock_run_command.return_value = (1, stdout, "")

        with pytest.raises(AgentRateLimitError):
            await run_opencode_agent(
                Path("/test"), "task", model="m", agent="plan-agent", retry_on_classified_failure=True
            )

        assert [call.args[0] for call in mock_sleep.await_args_list] == [5.0, 5.0]
