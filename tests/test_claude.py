import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.library.constants import CLAUDE_LINEAR_CREATE_TOOLS, CLAUDE_LINEAR_READ_TOOLS
from demetra.services.agents.claude import (
    _claude_project_slug,
    _claude_transcript_path,
    claude_compact_session,
    claude_session_exists,
    extract_claude_result,
    format_claude_stream_event,
    get_claude_session_tokens,
    load_claude_agent_definition,
    new_claude_session_id,
    run_claude_agent,
)
from demetra.settings import BASE_PATH, UV


class TestLoadClaudeAgentDefinition:
    def test_build_agent_base_tools_from_frontmatter(self):
        definition = load_claude_agent_definition("build-agent")

        assert {"Read", "Grep", "Glob", "Edit", "Write", "Bash", "mcp__demetra__*"} <= set(definition["tools"])
        assert definition["description"]
        assert "implement" in definition["prompt"].lower()

    def test_build_agent_has_no_linear_tools(self):
        definition = load_claude_agent_definition("build-agent")

        assert not (CLAUDE_LINEAR_READ_TOOLS & set(definition["tools"]))
        assert not (CLAUDE_LINEAR_CREATE_TOOLS & set(definition["tools"]))

    @pytest.mark.parametrize("agent", ["plan-agent", "resolve-agent", "research-agent"])
    def test_linear_read_tools_injected_for_read_agents(self, agent):
        definition = load_claude_agent_definition(agent)

        assert CLAUDE_LINEAR_READ_TOOLS <= set(definition["tools"])

    def test_linear_create_tools_only_on_research_agent(self):
        research = load_claude_agent_definition("research-agent")
        assert CLAUDE_LINEAR_CREATE_TOOLS <= set(research["tools"])

        for agent in ("plan-agent", "resolve-agent", "build-agent", "review-agent", "validate-agent"):
            definition = load_claude_agent_definition(agent)
            assert not (CLAUDE_LINEAR_CREATE_TOOLS & set(definition["tools"]))

    @pytest.mark.parametrize(
        "agent", ["plan-agent", "resolve-agent", "research-agent", "review-agent", "validate-agent"]
    )
    def test_disallowed_tools_include_edit_write_for_read_only_agents(self, agent):
        definition = load_claude_agent_definition(agent)

        assert "Bash(git commit:*)" in definition["disallowedTools"]
        assert "Bash(git push:*)" in definition["disallowedTools"]
        assert "Edit" in definition["disallowedTools"]
        assert "Write" in definition["disallowedTools"]

    @pytest.mark.parametrize("agent", ["build-agent", "merge-agent", "rebase-agent"])
    def test_disallowed_tools_exclude_edit_write_for_edit_agents(self, agent):
        definition = load_claude_agent_definition(agent)

        assert "Bash(git commit:*)" in definition["disallowedTools"]
        assert "Bash(git push:*)" in definition["disallowedTools"]
        assert "Edit" not in definition["disallowedTools"]
        assert "Write" not in definition["disallowedTools"]


class TestBuildClaudeMcpConfig:
    def test_returns_valid_json_with_expected_servers(self):
        raw = _build_config()

        assert raw["mcpServers"]["linear"] == {"type": "http", "url": "https://mcp.linear.app/mcp"}
        demetra_server = raw["mcpServers"]["demetra"]
        assert demetra_server["type"] == "stdio"
        assert demetra_server["command"] == str(UV["path"])
        assert "--directory" in demetra_server["args"]
        assert str(BASE_PATH) in demetra_server["args"]
        assert "--env-file" in demetra_server["args"]
        assert any(str(arg).endswith(".env") for arg in demetra_server["args"])

    def test_no_secret_value_present(self):
        from demetra.services.agents.claude import build_claude_mcp_config

        raw_string = build_claude_mcp_config()
        for needle in ("SECRET", "PASSWORD", "postgresql://", "DB_PASSWORD"):
            assert needle not in raw_string


def _build_config() -> dict:
    from demetra.services.agents.claude import build_claude_mcp_config

    return json.loads(build_claude_mcp_config())


class TestFormatClaudeStreamEvent:
    def test_system_init_event(self):
        line = json.dumps({"type": "system", "subtype": "init", "session_id": "abc", "model": "opus"})
        result = format_claude_stream_event(line)
        assert result is not None
        assert "abc" in result
        assert "opus" in result

    def test_assistant_text_block(self):
        line = json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello there"}]}})
        assert format_claude_stream_event(line) == "Hello there"

    def test_assistant_tool_use_block(self):
        line = json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "uv run pytest"}}]},
            }
        )
        result = format_claude_stream_event(line)
        assert result is not None
        assert "Bash" in result
        assert "uv run pytest" in result

    def test_user_tool_result_ok(self):
        line = json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "is_error": False}]}})
        assert format_claude_stream_event(line) == "[tool ok]"

    def test_user_tool_result_error(self):
        line = json.dumps(
            {
                "type": "user",
                "message": {
                    "content": [
                        {"type": "tool_result", "is_error": True, "content": "boom: file not found\nmore detail"}
                    ]
                },
            }
        )
        result = format_claude_stream_event(line)
        assert result is not None
        assert result.startswith("[tool error]")
        assert "boom: file not found" in result

    def test_result_event(self):
        line = json.dumps({"type": "result", "num_turns": 3, "duration_ms": 1200, "total_cost_usd": 0.05})
        result = format_claude_stream_event(line)
        assert result is not None
        assert "3 turns" in result
        assert "1200ms" in result
        assert "0.05" in result

    def test_unknown_event_type_returns_none(self):
        assert format_claude_stream_event(json.dumps({"type": "rate_limit_event"})) is None

    def test_malformed_json_returns_none(self):
        assert format_claude_stream_event("not json {{{") is None

    def test_empty_line_returns_none(self):
        assert format_claude_stream_event("") is None
        assert format_claude_stream_event("   \n") is None

    def test_non_dict_json_returns_none(self):
        assert format_claude_stream_event("[1, 2, 3]") is None


class TestExtractClaudeResult:
    def test_successful_run_parses_result_and_usage(self):
        stdout = "\n".join(
            [
                json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "working"}]}}),
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"path": "a.py"}}]},
                    }
                ),
                json.dumps(
                    {
                        "type": "result",
                        "is_error": False,
                        "subtype": "success",
                        "session_id": "sess-1",
                        "num_turns": 2,
                        "result": "All done.",
                        "usage": {
                            "input_tokens": 100,
                            "output_tokens": 50,
                            "cache_read_input_tokens": 10,
                            "cache_creation_input_tokens": 5,
                            "output_tokens_details": {"thinking_tokens": 7},
                        },
                        "permission_denials": [],
                    }
                ),
            ]
        )

        result = extract_claude_result(stdout)

        assert result.result == "All done."
        assert result.is_error is False
        assert result.subtype == "success"
        assert result.session_id == "sess-1"
        assert result.num_turns == 2
        assert result.usage is not None
        assert result.usage.input == 100
        assert result.usage.output == 50
        assert result.usage.cache_read == 10
        assert result.usage.cache_write == 5
        assert result.usage.reasoning == 7
        assert result.permission_denials == []

    def test_is_error_true(self):
        stdout = json.dumps({"type": "result", "is_error": True, "subtype": "error_during_execution", "result": ""})
        result = extract_claude_result(stdout)
        assert result.is_error is True
        assert result.subtype == "error_during_execution"

    def test_budget_exhausted_subtype(self):
        stdout = json.dumps(
            {"type": "result", "is_error": True, "subtype": "error_max_budget_usd", "errors": ["Reached max budget"]}
        )
        result = extract_claude_result(stdout)
        assert result.subtype == "error_max_budget_usd"
        assert result.is_error is True

    def test_missing_result_event_falls_back_to_assistant_text(self):
        stdout = "\n".join(
            [
                json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "partial "}]}}),
                json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "output"}]}}),
            ]
        )

        result = extract_claude_result(stdout)

        assert result.result == "partial \noutput"
        assert result.is_error is True
        assert result.subtype == "missing_result"
        assert result.session_id is None

    def test_permission_denials_dict_shaped(self):
        stdout = json.dumps(
            {
                "type": "result",
                "is_error": False,
                "subtype": "success",
                "result": "done",
                "permission_denials": [{"tool_name": "Bash"}, {"tool": "Edit"}],
            }
        )
        result = extract_claude_result(stdout)
        assert result.permission_denials == ["Bash", "Edit"]

    def test_permission_denials_bare_string_shaped(self):
        stdout = json.dumps(
            {
                "type": "result",
                "is_error": False,
                "subtype": "success",
                "result": "done",
                "permission_denials": ["Bash(git push:*)"],
            }
        )
        result = extract_claude_result(stdout)
        assert result.permission_denials == ["Bash(git push:*)"]

    def test_malformed_lines_are_skipped(self):
        stdout = "\n".join(
            [
                "not json",
                json.dumps({"type": "result", "is_error": False, "subtype": "success", "result": "ok"}),
            ]
        )
        result = extract_claude_result(stdout)
        assert result.result == "ok"


def _ndjson_result(**overrides) -> str:
    payload = {"type": "result", "is_error": False, "subtype": "success", "result": "done", "num_turns": 1}
    payload.update(overrides)
    return json.dumps(payload)


class TestRunClaudeAgentCommand:
    @pytest.fixture
    def mock_run_command(self):
        with patch("demetra.services.agents.claude.run_command", new_callable=AsyncMock) as mock:
            mock.return_value = (0, _ndjson_result(), "")
            yield mock

    @pytest.mark.asyncio
    async def test_builds_expected_command(self, mock_run_command):
        await run_claude_agent(
            target_path=Path("/tmp/worktree"),
            task="do the thing",
            model="opus",
            agent="build-agent",
            session_id="sess-1",
            resume=True,
            effort="xhigh",
            max_budget_usd=15.0,
            project_id="proj-1",
        )

        call_kwargs = mock_run_command.call_args.kwargs
        command = call_kwargs["command"]

        assert command[0].endswith("claude")
        assert "-p" in command
        assert command[command.index("--output-format") + 1] == "stream-json"
        assert command[command.index("--model") + 1] == "opus"
        assert command[command.index("--agent") + 1] == "build-agent"
        assert "--mcp-config" in command
        assert "--strict-mcp-config" in command
        assert command[command.index("--permission-mode") + 1] == "acceptEdits"
        assert command[command.index("--effort") + 1] == "xhigh"
        assert command[command.index("--max-budget-usd") + 1] == "15.0"
        assert command[command.index("--resume") + 1] == "sess-1"
        assert "--session-id" not in command

        agents_json = command[command.index("--agents") + 1]
        agents = json.loads(agents_json)
        assert set(agents.keys()) == {"build-agent"}

        allowed_index = command.index("--allowedTools")
        disallowed_index = command.index("--disallowedTools")
        assert allowed_index < disallowed_index

        # The task must be delivered via stdin, never argv.
        assert call_kwargs["input_text"] == "do the thing"
        assert all(arg != "do the thing" for arg in command)

    @pytest.mark.asyncio
    async def test_uses_session_id_when_not_resuming(self, mock_run_command):
        await run_claude_agent(
            target_path=Path("/tmp/worktree"),
            task="task",
            model="opus",
            agent="plan-agent",
            session_id="new-sess",
            resume=False,
        )

        command = mock_run_command.call_args.kwargs["command"]
        assert command[command.index("--session-id") + 1] == "new-sess"
        assert "--resume" not in command

    @pytest.mark.asyncio
    async def test_omits_effort_and_budget_when_none(self, mock_run_command):
        await run_claude_agent(target_path=Path("/tmp/worktree"), task="task", model="haiku", agent="validate-agent")

        command = mock_run_command.call_args.kwargs["command"]
        assert "--effort" not in command
        assert "--max-budget-usd" not in command
        assert "--session-id" not in command
        assert "--resume" not in command


class TestRunClaudeAgentFailureHandling:
    @pytest.fixture
    def mock_run_command(self):
        with patch("demetra.services.agents.claude.run_command", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_denials_alone_do_not_fail_the_run(self, mock_run_command):
        mock_run_command.return_value = (
            0,
            _ndjson_result(permission_denials=[{"tool_name": "Bash(git commit:*)"}]),
            "",
        )

        exit_code, result, _stderr = await run_claude_agent(
            target_path=Path("/tmp"), task="t", model="opus", agent="build-agent"
        )

        assert exit_code == 0
        assert result == "done"

    @pytest.mark.asyncio
    async def test_is_error_forces_nonzero_exit(self, mock_run_command):
        mock_run_command.return_value = (
            0,
            json.dumps({"type": "result", "is_error": True, "subtype": "error_during_execution", "result": ""}),
            "",
        )

        exit_code, _result, stderr = await run_claude_agent(
            target_path=Path("/tmp"), task="t", model="opus", agent="build-agent"
        )

        assert exit_code != 0
        assert "error_during_execution" in stderr

    @pytest.mark.parametrize("subtype", ["error_max_turns", "error_max_budget_usd", "error_during_execution"])
    @pytest.mark.asyncio
    async def test_failure_subtypes_force_nonzero_exit_even_if_is_error_false(self, mock_run_command, subtype):
        mock_run_command.return_value = (
            0,
            json.dumps({"type": "result", "is_error": False, "subtype": subtype, "result": ""}),
            "",
        )

        exit_code, _result, stderr = await run_claude_agent(
            target_path=Path("/tmp"), task="t", model="opus", agent="build-agent"
        )

        assert exit_code != 0
        assert subtype in stderr

    @pytest.mark.asyncio
    async def test_denials_reported_alongside_failure(self, mock_run_command):
        mock_run_command.return_value = (
            0,
            json.dumps(
                {
                    "type": "result",
                    "is_error": True,
                    "subtype": "error_during_execution",
                    "result": "",
                    "permission_denials": ["Bash(git push:*)"],
                }
            ),
            "",
        )

        exit_code, _result, stderr = await run_claude_agent(
            target_path=Path("/tmp"), task="t", model="opus", agent="build-agent"
        )

        assert exit_code != 0
        assert "Bash(git push:*)" in stderr


class TestClaudeSessionHelpers:
    def test_new_claude_session_id_is_a_valid_uuid4(self):
        session_id = new_claude_session_id()
        parsed = uuid.UUID(session_id)
        assert str(parsed) == session_id

    def test_project_slug_replaces_every_non_alphanumeric_character(self):
        slug = _claude_project_slug(Path("/private/tmp/claude.verify.dots"))
        assert slug == "-private-tmp-claude-verify-dots"

    @pytest.mark.asyncio
    async def test_claude_compact_session_is_a_noop(self):
        result = await claude_compact_session(Path("/tmp"), "sess-1")
        assert result == (0, "", "")

    @pytest.mark.asyncio
    async def test_session_exists_true_when_transcript_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        target_path = tmp_path / "worktree"
        target_path.mkdir()
        transcript_path = _claude_transcript_path(target_path=target_path, session_id="sess-1")
        transcript_path.parent.mkdir(parents=True)
        transcript_path.write_text("{}\n")

        assert await claude_session_exists(target_path=target_path, session_id="sess-1") is True

    @pytest.mark.asyncio
    async def test_session_exists_false_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        target_path = tmp_path / "worktree"
        target_path.mkdir()

        assert await claude_session_exists(target_path=target_path, session_id="missing") is False


class TestGetClaudeSessionTokens:
    @pytest.mark.asyncio
    async def test_sums_assistant_usage_and_reports_last_context(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        target_path = tmp_path / "worktree"
        target_path.mkdir()
        transcript_path = _claude_transcript_path(target_path=target_path, session_id="sess-1")
        transcript_path.parent.mkdir(parents=True)

        lines = [
            json.dumps({"message": {"role": "user"}}),
            json.dumps(
                {
                    "message": {
                        "role": "assistant",
                        "usage": {
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "cache_read_input_tokens": 2,
                            "cache_creation_input_tokens": 1,
                            "output_tokens_details": {"thinking_tokens": 3},
                        },
                    }
                }
            ),
            "not json, skip me",
            json.dumps(
                {
                    "message": {
                        "role": "assistant",
                        "usage": {
                            "input_tokens": 20,
                            "output_tokens": 8,
                            "cache_read_input_tokens": 4,
                            "cache_creation_input_tokens": 0,
                            "output_tokens_details": {"thinking_tokens": 1},
                        },
                    }
                }
            ),
        ]
        transcript_path.write_text("\n".join(lines) + "\n")

        usage = await get_claude_session_tokens(target_path=target_path, session_id="sess-1")

        assert usage is not None
        assert usage.input == 30
        assert usage.output == 13
        assert usage.cache_read == 6
        assert usage.cache_write == 1
        assert usage.reasoning == 4
        assert usage.context == 24  # last line: 20 + 4

    @pytest.mark.asyncio
    async def test_returns_none_when_transcript_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        target_path = tmp_path / "worktree"
        target_path.mkdir()

        usage = await get_claude_session_tokens(target_path=target_path, session_id="missing")

        assert usage is None
