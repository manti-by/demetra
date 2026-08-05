import json
from pathlib import Path

from demetra.library.models import TokenUsage
from demetra.services.prompt import get_prompt
from demetra.services.subprocess import run_command, run_command_to_file
from demetra.services.tui import print_message
from demetra.services.utils import non_negative_int
from demetra.settings import OPENCODE


PLAN_HEADER_STRING = "## Implementation Plan"
PLAN_IS_READY_STRING = "Ready to proceed to build."
PLAN_HAS_QUESTIONS = "Please check my questions above."


async def opencode_plan_agent(
    target_path: Path, task: str, task_title: str | None = None, env: dict[str, str] | None = None
) -> tuple[int, str, str]:
    """Run the opencode plan agent with plan-output formatting rules.

    Appends instructions to avoid markdown tables and to signal readiness or
    open questions with the terminal markers.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        task_title: Optional session title.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    task += (
        f"\nIMPORTANT:"
        f"\n- Do NOT use markdown tables in the implementation plan. Use lists or paragraphs instead."
        f"\n- If you have some question about implementation, just print in the end `{PLAN_HAS_QUESTIONS}`"
        f"\n- If there are no questions, just print in the end `{PLAN_IS_READY_STRING}`"
    )

    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        model=OPENCODE["plan_model"],
        agent="plan-agent",
        env=env,
    )


async def opencode_build_agent(
    target_path: Path,
    task: str,
    session_id: str | None = None,
    task_title: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run the opencode build agent, forbidding commits and pushes.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        session_id: Optional session id to continue.
        task_title: Optional session title.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    task += "\nDO NOT commit or push any changes, just stage them"
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        session_id=session_id,
        task_title=task_title,
        model=OPENCODE["build_model"],
        agent="build-agent",
        env=env,
    )


async def opencode_review_agent(
    target_path: Path, model: str, task_title: str | None = None, env: dict[str, str] | None = None
) -> tuple[int, str, str]:
    """Run the opencode review agent with the review prompt.

    Args:
        target_path: Directory to run the agent in.
        model: The model to use for the review.
        task_title: Optional session title.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    task = await get_prompt(name="review_agent")
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        model=model,
        agent="review-agent",
        env=env,
    )


async def opencode_validate_agent(
    target_path: Path, build_plan: str, task_title: str | None = None, env: dict[str, str] | None = None
) -> tuple[int, str, str]:
    """Run the opencode validate agent with the validate prompt and build plan.

    The entire build plan is appended to the validate prompt and delivered via
    stdin, so no plan step is dropped for length.

    Args:
        target_path: Directory to run the agent in.
        build_plan: The finalized build plan to check coverage against.
        task_title: Optional session title.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    task = await get_prompt(name="validate_agent")
    task += f"\n\nBuild Plan:\n{build_plan}"
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        model=OPENCODE["validate_model"],
        agent="validate-agent",
        env=env,
    )


async def opencode_merge_agent(target_path: Path, task: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Run the opencode merge agent to resolve merge conflicts.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        model=OPENCODE["build_model"],
        agent="merge-agent",
        env=env,
    )


async def opencode_resolve_agent(
    target_path: Path, task: str, task_title: str | None = None, env: dict[str, str] | None = None
) -> tuple[int, str, str]:
    """Run the opencode resolve agent to answer open plan questions.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        task_title: Optional session title.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        model=OPENCODE["resolve_model"],
        agent="resolve-agent",
        env=env,
    )


async def run_opencode_agent(
    target_path: Path,
    task: str,
    model: str,
    agent: str,
    session_id: str | None = None,
    task_title: str | None = None,
    disable_stdio: bool = False,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run an opencode agent with the given model, task and session options.

    The task prompt is delivered to the ``opencode run`` message slot via stdin,
    so arbitrarily long prompts (e.g. full build plans) reach the agent intact
    instead of being truncated to fit a command-line argument.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        model: The model to use.
        agent: The agent name, e.g. ``"plan-agent"``.
        session_id: Optional session id to continue.
        task_title: Optional session title.
        disable_stdio: Whether to suppress live subprocess output.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    command = [str(OPENCODE["path"]), "run", "--dir", str(target_path), "--model", model, "--agent", agent]

    if session_id is not None:
        command.extend(["--session", session_id])
    if task_title is not None:
        command.extend(["--title", task_title])

    return await run_command(
        command=command,
        target_path=target_path,
        disable_stdio=disable_stdio,
        env=env,
        input_text=task,
    )


async def get_opencode_sessions(target_path: Path, env: dict[str, str] | None = None) -> list[dict[str, str]]:
    """List opencode sessions as JSON records.

    Args:
        target_path: Directory to run the opencode CLI in.
        env: Optional environment overrides for the subprocess.

    Returns:
        list[dict[str, str]]: The parsed session list.
    """
    command = [str(OPENCODE["path"]), "session", "list", "--format", "json"]
    _, result, _ = await run_command(command=command, target_path=target_path, disable_stdio=True, env=env)
    return json.loads(result)


async def get_opencode_session_id(target_path: Path, task_title: str, env: dict[str, str] | None = None) -> str | None:
    """Find the opencode session id for a task title, preferring matching directory.

    Sessions are matched by title; among matches the newest one for the same
    working directory wins, with the newest overall session as a fallback.

    Args:
        target_path: Directory to run the opencode CLI in.
        task_title: The task title to match sessions on.
        env: Optional environment overrides for the subprocess.

    Returns:
        str | None: The session id, or None when no matching session exists.
    """
    sessions = await get_opencode_sessions(target_path=target_path, env=env)
    filtered_sessions = list(filter(lambda x: task_title == x.get("title", ""), sessions))
    if not filtered_sessions:
        print_message("Session not found", style="info")

    fallback_session_id = None
    target_directory = str(target_path).rstrip("/")
    for session in sorted(filtered_sessions, key=lambda x: x["updated"], reverse=True):
        if not fallback_session_id:
            fallback_session_id = session["id"]

        session_directory = session.get("directory", "").rstrip("/")
        if session_directory == target_directory:
            return session["id"]

    if fallback_session_id:
        print_message("Worktree mistmatch, using fallback session id", style="error")
    return fallback_session_id


async def get_opencode_session_tokens(
    target_path: Path, session_id: str, env: dict[str, str] | None = None
) -> TokenUsage | None:
    """Read the token usage breakdown of an opencode session via export.

    Returns a TokenUsage with input, output, reasoning, cache read/write, and
    context (the current context window size derived from the last assistant
    message).

    Args:
        target_path: Directory to run the opencode CLI in.
        session_id: The opencode session id.
        env: Optional environment overrides for the subprocess.

    Returns:
        TokenUsage | None: The token usage, or None when the export fails or
            the JSON is malformed.
    """
    command = [str(OPENCODE["path"]), "export", session_id]
    exit_code, result, _ = await run_command_to_file(
        command=command, target_path=target_path, disable_stdio=True, env=env
    )
    if exit_code != 0:
        return None

    try:
        data = json.loads(result)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None

    info = data.get("info")
    if not isinstance(info, dict):
        return None

    tokens = info.get("tokens")
    if not isinstance(tokens, dict):
        return None

    input_tokens = non_negative_int(tokens.get("input"))
    output_tokens = non_negative_int(tokens.get("output"))
    reasoning_tokens = non_negative_int(tokens.get("reasoning"))
    if input_tokens is None or output_tokens is None or reasoning_tokens is None:
        return None

    usage = TokenUsage(
        input=input_tokens,
        output=output_tokens,
        reasoning=reasoning_tokens,
    )
    cache = tokens.get("cache")
    if isinstance(cache, dict):
        cache_read = non_negative_int(cache.get("read"))
        cache_write = non_negative_int(cache.get("write"))
        if cache_read is not None:
            usage.cache_read = cache_read
        if cache_write is not None:
            usage.cache_write = cache_write

    messages = data.get("messages")
    if isinstance(messages, list):
        latest: dict | None = None
        latest_ts: str | None = None
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            msg_info = msg.get("info")
            if not isinstance(msg_info, dict):
                continue
            if msg_info.get("role") != "assistant":
                continue
            msg_tokens = msg_info.get("tokens")
            if not isinstance(msg_tokens, dict):
                continue
            msg_input = non_negative_int(msg_tokens.get("input"))
            msg_output = non_negative_int(msg_tokens.get("output"))
            if msg_input is None or not (msg_input > 0 or (msg_output is not None and msg_output > 0)):
                continue
            msg_ts = msg.get("timestamp") or msg_info.get("timestamp")
            if latest_ts is None or (msg_ts is not None and msg_ts > latest_ts):
                latest = msg
                latest_ts = msg_ts
        if latest is not None:
            msg_tokens = latest["info"]["tokens"]
            msg_input = non_negative_int(msg_tokens.get("input"))
            msg_cache = msg_tokens.get("cache")
            msg_cache_read = 0
            if isinstance(msg_cache, dict):
                msg_cache_read = non_negative_int(msg_cache.get("read")) or 0
            if msg_input is not None:
                usage.context = msg_input + msg_cache_read

    return usage


async def get_opencode_session_length(
    target_path: Path, session_id: str, env: dict[str, str] | None = None
) -> int | None:
    """Return the total token count used by an opencode session.

    Args:
        target_path: Directory to run the opencode CLI in.
        session_id: The opencode session id.
        env: Optional environment overrides for the subprocess.

    Returns:
        int | None: The total token count, or None when unavailable.
    """
    usage = await get_opencode_session_tokens(target_path=target_path, session_id=session_id, env=env)
    return usage.total if usage is not None else None


async def opencode_compact_session(
    target_path: Path, session_id: str, env: dict[str, str] | None = None
) -> tuple[int, str, str]:
    """Run the ``/compact`` command within an existing opencode session.

    Args:
        target_path: Directory to run the opencode CLI in.
        session_id: The opencode session id to compact.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    command = [
        str(OPENCODE["path"]),
        "run",
        "--session",
        session_id,
        "--dir",
        str(target_path),
        "/compact",
    ]
    return await run_command(command=command, target_path=target_path, disable_stdio=False, env=env)


async def extract_plan(plan_output: str) -> str:
    """Slice the implementation plan section out of a plan agent output.

    Trims leading text before the plan header and strips any trailing
    readiness or question marker.

    Args:
        plan_output: The raw plan agent output.

    Returns:
        str: The extracted plan text.
    """
    if (start_index := plan_output.find(PLAN_HEADER_STRING)) != -1:
        plan_output = plan_output[start_index:]

    for end_string in (PLAN_IS_READY_STRING, PLAN_HAS_QUESTIONS):
        if (end_index := plan_output.find(end_string)) != -1:
            plan_output = plan_output[:end_index]
            break

    return plan_output.strip()
