import json
import re
from pathlib import Path
from uuid import uuid4

import aiofiles
import yaml

from demetra.library.constants import (
    CLAUDE_LINEAR_CREATE_TOOLS,
    CLAUDE_LINEAR_READ_TOOLS,
    PLAN_HAS_QUESTIONS,
    PLAN_IS_READY_STRING,
)
from demetra.library.models import ClaudeResult, SessionEnvironment, TokenUsage
from demetra.services.llm.prompt import get_prompt
from demetra.services.runtime.subprocess import run_command
from demetra.services.runtime.tui import print_message
from demetra.services.runtime.utils import non_negative_int
from demetra.settings import BASE_PATH, CLAUDE, CLAUDE_IDLE_TIMEOUT, CLAUDE_MAX_BUDGET_USD, UV


# Denied on every agent regardless of its own tool policy; the orchestrator
# owns commits and pushes, not the agent.
CLAUDE_DENIED_TOOLS: tuple[str, ...] = ("Bash(git commit:*)", "Bash(git push:*)")

# Result subtypes that fail the run even when is_error is False on the wire.
CLAUDE_FAILURE_SUBTYPES: frozenset[str] = frozenset(
    {"error_max_turns", "error_max_budget_usd", "error_during_execution"}
)

# Agent names whose base tool set (from .claude/agents/<name>.md) gets Linear
# and/or web tools injected at runtime, by exact tool name (never a wildcard).
_LINEAR_READ_AGENTS: frozenset[str] = frozenset({"plan-agent", "resolve-agent", "research-agent"})
_LINEAR_CREATE_AGENTS: frozenset[str] = frozenset({"research-agent"})


def _parse_agent_frontmatter(text: str) -> tuple[dict, str]:
    """Split a ``.claude/agents/*.md`` file into its YAML frontmatter and body.

    Args:
        text: The full file contents.

    Returns:
        tuple[dict, str]: The parsed frontmatter mapping and the body text
            (the system prompt), stripped.
    """
    if not text.startswith("---"):
        return {}, text.strip()

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text.strip()

    frontmatter = yaml.safe_load(parts[1]) or {}
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    return frontmatter, parts[2].strip()


def load_claude_agent_definition(agent: str) -> dict:
    """Load and assemble a Claude subagent definition for ``--agents``.

    Parses ``.claude/agents/<agent>.md`` (a Demetra asset addressed from
    ``BASE_PATH``, not the worktree), then injects the Linear and web tools
    the agent needs by exact tool name, and the shared commit/push deny list.

    Args:
        agent: The agent name, e.g. ``"build-agent"``.

    Returns:
        dict: The agent definition ready to serialize under ``--agents``.
    """
    path = BASE_PATH / ".claude" / "agents" / f"{agent}.md"
    frontmatter, body = _parse_agent_frontmatter(path.read_text())

    tools = list(frontmatter.get("tools") or [])
    if agent in _LINEAR_READ_AGENTS:
        tools.extend(sorted(CLAUDE_LINEAR_READ_TOOLS))
    if agent in _LINEAR_CREATE_AGENTS:
        tools.extend(sorted(CLAUDE_LINEAR_CREATE_TOOLS))

    disallowed_tools = list(CLAUDE_DENIED_TOOLS)
    for tool in ("Edit", "Write"):
        if tool not in tools:
            disallowed_tools.append(tool)

    return {
        "description": frontmatter.get("description", ""),
        "prompt": body,
        "tools": tools,
        "disallowedTools": disallowed_tools,
    }


def build_claude_mcp_config(project_id: str | None = None) -> str:
    """Build the inline ``--mcp-config`` JSON for a Claude agent run.

    The Demetra MCP server is launched with ``--directory`` (cwd is the
    worktree, not Demetra) and ``--env-file`` so its subprocess has DB
    credentials despite only inheriting the allowlisted OS env. No secret
    value is ever written into the JSON or argv; the env file path is a
    reference the ``uv`` subprocess reads itself.

    Args:
        project_id: Reserved for future per-project MCP scoping.

    Returns:
        str: The JSON-encoded MCP server configuration.
    """
    config = {
        "mcpServers": {
            "demetra": {
                "type": "stdio",
                "command": str(UV["path"]),
                "args": [
                    "--directory",
                    str(BASE_PATH),
                    "run",
                    "--env-file",
                    str(BASE_PATH / ".env"),
                    "python",
                    "-m",
                    "demetra.mcp_server",
                ],
            },
            "linear": {
                "type": "http",
                "url": "https://mcp.linear.app/mcp",
            },
        }
    }
    return json.dumps(config)


def _summarize_tool_input(tool_input: object) -> str:
    """Render a tool_use input as a short single-line summary for display.

    Args:
        tool_input: The tool's input payload, usually a dict.

    Returns:
        str: A short, single-line summary, truncated for display.
    """
    if not isinstance(tool_input, dict):
        return ""
    for key in ("command", "file_path", "path", "pattern", "query", "url"):
        if tool_input.get(key):
            value = str(tool_input[key]).replace("\n", " ")
            return value[:150]
    return ""


def _first_line_of_tool_result(content: object) -> str:
    """Extract the first line of a tool_result content payload for display.

    Args:
        content: The tool_result's content, a string or a list of blocks.

    Returns:
        str: The first non-empty line, truncated for display, or "".
    """
    text = ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = str(block.get("text") or "")
                break
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:200]
    return ""


def format_claude_stream_event(line: str) -> str | None:
    """Format one ``stream-json`` event line into a readable display line.

    A pure formatter: unknown event types, unknown fields and malformed JSON
    are all ignored by returning None instead of raising, since the
    stream-json schema is not a stable contract.

    Args:
        line: One raw NDJSON line from the Claude CLI's stdout.

    Returns:
        str | None: A display line, or None to skip this line.
    """
    line = line.strip()
    if not line:
        return None
    try:
        event = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(event, dict):
        return None

    event_type = event.get("type")

    if event_type == "system" and event.get("subtype") == "init":
        return f"Claude session {event.get('session_id', '?')} started (model {event.get('model', '?')})"

    if event_type == "assistant":
        message = event.get("message")
        if not isinstance(message, dict):
            return None
        rendered: list[str] = []
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text" and block.get("text"):
                rendered.append(str(block["text"]))
            elif block_type == "tool_use":
                summary = _summarize_tool_input(block.get("input"))
                name = block.get("name", "?")
                rendered.append(f"→ {name} {summary}".rstrip())
        return "\n".join(rendered) if rendered else None

    if event_type == "user":
        message = event.get("message")
        if not isinstance(message, dict):
            return None
        rendered = []
        for block in message.get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            if block.get("is_error"):
                detail = _first_line_of_tool_result(block.get("content"))
                rendered.append(f"✗ {detail}".rstrip())
            else:
                rendered.append("✓")
        return "\n".join(rendered) if rendered else None

    if event_type == "result":
        turns = event.get("num_turns", "?")
        duration = event.get("duration_ms", "?")
        cost = event.get("total_cost_usd", "?")
        return f"Claude run finished: {turns} turns, {duration}ms, ${cost}"

    return None


def extract_claude_result(stdout: str) -> ClaudeResult:
    """Parse the last ``result`` event out of a Claude ``stream-json`` run.

    Falls back to the concatenated assistant text (marked as an error) when
    no result event is present, e.g. after a crash or a kill on timeout.

    Args:
        stdout: The full captured stdout of the run (NDJSON lines).

    Returns:
        ClaudeResult: The parsed result, error state, session id and usage.
    """
    assistant_texts: list[str] = []
    last_result: dict | None = None

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(event, dict):
            continue

        if event.get("type") == "assistant":
            message = event.get("message")
            if isinstance(message, dict):
                for block in message.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                        assistant_texts.append(str(block["text"]))

        if event.get("type") == "result":
            last_result = event

    if last_result is None:
        return ClaudeResult(
            result="\n".join(assistant_texts).strip(),
            is_error=True,
            session_id=None,
            usage=None,
            subtype="missing_result",
            num_turns=0,
            permission_denials=[],
        )

    usage_data = last_result.get("usage")
    usage = None
    if isinstance(usage_data, dict):
        details = usage_data.get("output_tokens_details")
        reasoning_tokens = non_negative_int(details.get("thinking_tokens")) if isinstance(details, dict) else None
        usage = TokenUsage(
            input=non_negative_int(usage_data.get("input_tokens")) or 0,
            output=non_negative_int(usage_data.get("output_tokens")) or 0,
            reasoning=reasoning_tokens or 0,
            cache_read=non_negative_int(usage_data.get("cache_read_input_tokens")) or 0,
            cache_write=non_negative_int(usage_data.get("cache_creation_input_tokens")) or 0,
        )

    denials: list[str] = []
    for denial in last_result.get("permission_denials") or []:
        if isinstance(denial, dict):
            denials.append(str(denial.get("tool_name") or denial.get("tool") or "unknown"))
        elif isinstance(denial, str):
            denials.append(denial)

    return ClaudeResult(
        result=str(last_result.get("result") or "").strip(),
        is_error=bool(last_result.get("is_error", False)),
        session_id=last_result.get("session_id"),
        usage=usage,
        subtype=str(last_result.get("subtype") or ""),
        num_turns=non_negative_int(last_result.get("num_turns")) or 0,
        permission_denials=denials,
    )


async def run_claude_agent(
    target_path: Path,
    task: str,
    model: str,
    agent: str,
    session_id: str | None = None,
    resume: bool = False,
    effort: str | None = None,
    max_budget_usd: float | None = None,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    disable_stdio: bool = False,
) -> tuple[int, str, str]:
    """Run a Claude Code agent with the given model, task and session options.

    The task prompt is delivered via stdin, mirroring the OpenCode wrapper, so
    arbitrarily long prompts reach the agent intact. Live progress is rendered
    from ``stream-json`` events via :func:`format_claude_stream_event`; the
    final result is parsed via :func:`extract_claude_result`. The Claude CLI
    has no turn-cap flag, so a per-run USD budget (``--max-budget-usd``) is the
    real bound against a looping or runaway agent, together with the idle
    watchdog on the subprocess stdout stream.

    Args:
        target_path: Directory to run the agent in (the worktree).
        task: The task prompt for the agent, delivered via stdin.
        model: The model to use, e.g. ``"opus"``.
        agent: The agent name, e.g. ``"plan-agent"``.
        session_id: Optional session id to start or resume.
        resume: When True and session_id is given, resume with ``--resume``
            instead of starting a fresh session with ``--session-id``.
        effort: Optional effort level; omitted from the command when None.
        max_budget_usd: Optional USD budget cap; omitted when None.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        disable_stdio: Whether to suppress live subprocess output.

    Returns:
        tuple[int, str, str]: Exit code, the agent's final result text (not
            the raw stream) and stderr, matching the OpenCode wrapper contract.
    """
    agent_definition = load_claude_agent_definition(agent)

    command = [
        str(CLAUDE["path"]),
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        model,
        "--agents",
        json.dumps({agent: agent_definition}),
        "--agent",
        agent,
        "--mcp-config",
        build_claude_mcp_config(project_id=project_id),
        "--strict-mcp-config",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        *agent_definition["tools"],
        "--disallowedTools",
        *agent_definition["disallowedTools"],
    ]
    if effort is not None:
        command.extend(["--effort", effort])
    if max_budget_usd is not None:
        command.extend(["--max-budget-usd", str(max_budget_usd)])
    if session_id is not None:
        if resume:
            command.extend(["--resume", session_id])
        else:
            command.extend(["--session-id", session_id])

    exit_code, stdout, stderr = await run_command(
        command=command,
        target_path=target_path,
        disable_stdio=disable_stdio,
        env=env,
        input_text=task,
        project_id=project_id,
        line_formatter=format_claude_stream_event,
        idle_timeout=CLAUDE_IDLE_TIMEOUT,
    )

    parsed = extract_claude_result(stdout)
    for denial in parsed.permission_denials:
        print_message(f"Claude agent {agent!r} denied tool: {denial}", style="warning")

    failed = parsed.is_error or parsed.subtype in CLAUDE_FAILURE_SUBTYPES
    if failed:
        if exit_code == 0:
            exit_code = 1
        detail = f"subtype={parsed.subtype or 'unknown'} turns={parsed.num_turns}"
        if parsed.permission_denials:
            detail += f" denied_tools={','.join(parsed.permission_denials)}"
        stderr = f"{stderr}\n" if stderr else ""
        stderr += f"Claude agent {agent} stopped: {detail}"

    return exit_code, parsed.result, stderr


async def claude_plan_agent(
    target_path: Path,
    task: str,
    session_id: str | None = None,
    task_title: str | None = None,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the Claude plan agent with plan-output formatting rules.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        session_id: The freshly generated session id for this plan run.
        task_title: Reserved; Claude sessions are addressed by id, not title.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    task += (
        f"\nIMPORTANT:"
        f"\n- Do NOT use markdown tables in the implementation plan. Use lists or paragraphs instead."
        f"\n- If you have some question about implementation, just print in the end `{PLAN_HAS_QUESTIONS}`"
        f"\n- If there are no questions, just print in the end `{PLAN_IS_READY_STRING}`"
    )
    model = environment.claude_plan_model if environment is not None else CLAUDE["plan_model"]
    effort = environment.claude_effort("plan") if environment is not None else CLAUDE["plan_effort"]
    budget = environment.claude_max_budget_usd("plan") if environment is not None else CLAUDE_MAX_BUDGET_USD["plan"]
    return await run_claude_agent(
        target_path=target_path,
        task=task,
        model=model,
        agent="plan-agent",
        session_id=session_id,
        effort=effort,
        max_budget_usd=budget,
        env=env,
        project_id=project_id,
    )


async def claude_build_agent(
    target_path: Path,
    task: str,
    session_id: str | None = None,
    task_title: str | None = None,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the Claude build agent, forbidding commits and pushes.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        session_id: Optional session id to continue.
        task_title: Reserved; Claude sessions are addressed by id, not title.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    task += "\nDO NOT commit or push any changes, just stage them"
    model = environment.claude_build_model if environment is not None else CLAUDE["build_model"]
    effort = environment.claude_effort("build") if environment is not None else CLAUDE["build_effort"]
    budget = environment.claude_max_budget_usd("build") if environment is not None else CLAUDE_MAX_BUDGET_USD["build"]

    resume = False
    if session_id is not None:
        resume = await claude_session_exists(target_path=target_path, session_id=session_id)
        if not resume:
            print_message("Claude session transcript missing, starting a fresh session.", style="warning")

    return await run_claude_agent(
        target_path=target_path,
        task=task,
        model=model,
        agent="build-agent",
        session_id=session_id,
        resume=resume,
        effort=effort,
        max_budget_usd=budget,
        env=env,
        project_id=project_id,
    )


async def claude_review_agent(
    target_path: Path,
    model: str,
    effort: str | None = None,
    max_budget_usd: float | None = None,
    task_title: str | None = None,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
) -> tuple[int, str, str]:
    """Run the Claude review agent with the review prompt.

    Args:
        target_path: Directory to run the agent in.
        model: The model to use for this review run.
        effort: The effort level for this review run, if any.
        max_budget_usd: The USD budget cap for this review run; defaults to
            the settings default when None.
        task_title: Reserved; Claude sessions are addressed by id, not title.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    task = await get_prompt(name="review_agent")
    budget = max_budget_usd if max_budget_usd is not None else CLAUDE_MAX_BUDGET_USD["review"]
    return await run_claude_agent(
        target_path=target_path,
        task=task,
        model=model,
        agent="review-agent",
        effort=effort,
        max_budget_usd=budget,
        env=env,
        project_id=project_id,
    )


async def claude_validate_agent(
    target_path: Path,
    build_plan: str,
    task_title: str | None = None,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the Claude validate agent with the validate prompt and build plan.

    Args:
        target_path: Directory to run the agent in.
        build_plan: The finalized build plan to check coverage against.
        task_title: Reserved; Claude sessions are addressed by id, not title.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    task = await get_prompt(name="validate_agent")
    task += f"\n\nBuild Plan:\n{build_plan}"
    model = environment.claude_validate_model if environment is not None else CLAUDE["validate_model"]
    effort = environment.claude_effort("validate") if environment is not None else CLAUDE["validate_effort"]
    budget = (
        environment.claude_max_budget_usd("validate") if environment is not None else CLAUDE_MAX_BUDGET_USD["validate"]
    )
    return await run_claude_agent(
        target_path=target_path,
        task=task,
        model=model,
        agent="validate-agent",
        effort=effort,
        max_budget_usd=budget,
        env=env,
        project_id=project_id,
    )


async def claude_review_fixes_agent(
    target_path: Path,
    task: str,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the Claude build-agent with the fix-review-findings skill.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt including unresolved review thread details.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    task = f"Use the fix-review-findings skill to address all unresolved review findings.\n\n{task}"
    task += "\nDO NOT commit or push any changes, just stage them"
    model = environment.claude_build_model if environment is not None else CLAUDE["build_model"]
    effort = environment.claude_effort("build") if environment is not None else CLAUDE["build_effort"]
    budget = environment.claude_max_budget_usd("build") if environment is not None else CLAUDE_MAX_BUDGET_USD["build"]
    return await run_claude_agent(
        target_path=target_path,
        task=task,
        model=model,
        agent="build-agent",
        effort=effort,
        max_budget_usd=budget,
        env=env,
        project_id=project_id,
    )


async def claude_merge_agent(
    target_path: Path,
    task: str,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the Claude merge agent to resolve merge conflicts.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    model = environment.claude_build_model if environment is not None else CLAUDE["build_model"]
    effort = environment.claude_effort("build") if environment is not None else CLAUDE["build_effort"]
    budget = environment.claude_max_budget_usd("build") if environment is not None else CLAUDE_MAX_BUDGET_USD["build"]
    return await run_claude_agent(
        target_path=target_path,
        task=task,
        model=model,
        agent="merge-agent",
        effort=effort,
        max_budget_usd=budget,
        env=env,
        project_id=project_id,
    )


async def claude_rebase_agent(
    target_path: Path,
    task: str,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the Claude rebase agent to resolve rebase conflicts.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    model = environment.claude_build_model if environment is not None else CLAUDE["build_model"]
    effort = environment.claude_effort("build") if environment is not None else CLAUDE["build_effort"]
    budget = environment.claude_max_budget_usd("build") if environment is not None else CLAUDE_MAX_BUDGET_USD["build"]
    return await run_claude_agent(
        target_path=target_path,
        task=task,
        model=model,
        agent="rebase-agent",
        effort=effort,
        max_budget_usd=budget,
        env=env,
        project_id=project_id,
    )


async def claude_resolve_agent(
    target_path: Path,
    task: str,
    task_title: str | None = None,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the Claude resolve agent to answer open plan questions.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        task_title: Reserved; Claude sessions are addressed by id, not title.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    model = environment.claude_resolve_model if environment is not None else CLAUDE["resolve_model"]
    effort = environment.claude_effort("resolve") if environment is not None else CLAUDE["resolve_effort"]
    budget = (
        environment.claude_max_budget_usd("resolve") if environment is not None else CLAUDE_MAX_BUDGET_USD["resolve"]
    )
    return await run_claude_agent(
        target_path=target_path,
        task=task,
        model=model,
        agent="resolve-agent",
        effort=effort,
        max_budget_usd=budget,
        env=env,
        project_id=project_id,
    )


async def claude_research_agent(
    target_path: Path,
    task: str,
    task_title: str | None = None,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the Claude research agent to validate a ticket against wiki and web.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        task_title: Reserved; Claude sessions are addressed by id, not title.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    prompt = await get_prompt(name="research_agent", task=task)
    model = environment.claude_research_model if environment is not None else CLAUDE["research_model"]
    effort = environment.claude_effort("research") if environment is not None else CLAUDE["research_effort"]
    budget = (
        environment.claude_max_budget_usd("research") if environment is not None else CLAUDE_MAX_BUDGET_USD["research"]
    )
    return await run_claude_agent(
        target_path=target_path,
        task=prompt,
        model=model,
        agent="research-agent",
        effort=effort,
        max_budget_usd=budget,
        env=env,
        project_id=project_id,
    )


def new_claude_session_id() -> str:
    """Generate a new Claude session id to pass via ``--session-id``.

    Returns:
        str: A fresh uuid4 string.
    """
    return str(uuid4())


def _claude_project_slug(target_path: Path) -> str:
    """Return the ``~/.claude/projects/<slug>`` slug for a working directory.

    Claude Code slugs the resolved absolute path by replacing every character
    that is not a letter or digit with a hyphen (verified against the
    installed CLI).

    Args:
        target_path: The working directory the agent was run in.

    Returns:
        str: The project directory slug.
    """
    return re.sub(r"[^A-Za-z0-9]", "-", str(Path(target_path).resolve()))


def _claude_transcript_path(target_path: Path, session_id: str) -> Path:
    """Return the transcript path for a Claude session.

    Args:
        target_path: The working directory the agent was run in.
        session_id: The Claude session id.

    Returns:
        Path: The expected ``.jsonl`` transcript path under ``~/.claude``.
    """
    return Path.home() / ".claude" / "projects" / _claude_project_slug(target_path) / f"{session_id}.jsonl"


async def claude_session_exists(target_path: Path, session_id: str) -> bool:
    """Return whether a Claude session transcript exists on disk.

    Used to fall back from ``--resume`` to a fresh ``--session-id`` when the
    worktree was recreated and the prior transcript is gone.

    Args:
        target_path: The working directory the agent was run in.
        session_id: The Claude session id.

    Returns:
        bool: True when the transcript file exists.
    """
    return _claude_transcript_path(target_path=target_path, session_id=session_id).is_file()


async def get_claude_session_tokens(target_path: Path, session_id: str) -> TokenUsage | None:
    """Read the token usage breakdown of a Claude session via its transcript.

    Sums ``input``, ``output``, ``reasoning``, ``cache_read`` and
    ``cache_write`` from every assistant message's usage in the transcript;
    ``context`` is the last assistant message's ``input_tokens +
    cache_read_input_tokens``.

    Args:
        target_path: The working directory the agent was run in.
        session_id: The Claude session id.

    Returns:
        TokenUsage | None: The token usage, or None when the transcript is
            missing or malformed.
    """
    transcript_path = _claude_transcript_path(target_path=target_path, session_id=session_id)
    if not transcript_path.is_file():
        return None

    usage = TokenUsage()
    last_input: int | None = None
    last_cache_read = 0
    try:
        async with aiofiles.open(transcript_path) as f:
            async for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    record = json.loads(raw_line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if not isinstance(record, dict):
                    continue
                message = record.get("message")
                if not isinstance(message, dict) or message.get("role") != "assistant":
                    continue
                message_usage = message.get("usage")
                if not isinstance(message_usage, dict):
                    continue

                input_tokens = non_negative_int(message_usage.get("input_tokens")) or 0
                output_tokens = non_negative_int(message_usage.get("output_tokens")) or 0
                cache_read = non_negative_int(message_usage.get("cache_read_input_tokens")) or 0
                cache_write = non_negative_int(message_usage.get("cache_creation_input_tokens")) or 0
                thinking_tokens = 0
                details = message_usage.get("output_tokens_details")
                if isinstance(details, dict):
                    thinking_tokens = non_negative_int(details.get("thinking_tokens")) or 0

                usage.input += input_tokens
                usage.output += output_tokens
                usage.reasoning += thinking_tokens
                usage.cache_read += cache_read
                usage.cache_write += cache_write
                last_input = input_tokens
                last_cache_read = cache_read
    except OSError:
        return None

    if last_input is not None:
        usage.context = last_input + last_cache_read
    return usage


async def claude_compact_session(
    target_path: Path, session_id: str, env: dict[str, str] | None = None
) -> tuple[int, str, str]:
    """No-op compaction hook for the Claude harness.

    Claude Code auto-compacts long sessions on its own; there is no explicit
    ``/compact`` step to run out-of-band, unlike OpenCode.

    Args:
        target_path: Reserved, for interface parity with the OpenCode wrapper.
        session_id: Reserved, for interface parity with the OpenCode wrapper.
        env: Reserved, for interface parity with the OpenCode wrapper.

    Returns:
        tuple[int, str, str]: Always ``(0, "", "")``.
    """
    return 0, "", ""
