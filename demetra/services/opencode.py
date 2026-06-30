import json
import shlex
from pathlib import Path

from demetra.services.prompt import get_prompt
from demetra.services.subprocess import run_command
from demetra.services.tui import print_message
from demetra.settings import OPENCODE


PLAN_HEADER_STRING = "## Implementation Plan"
PLAN_IS_READY_STRING = "Ready to proceed to build."
PLAN_HAS_QUESTIONS = "Please check my questions above."


async def opencode_plan_agent(
    target_path: Path, task: str, task_title: str | None = None, env: dict[str, str] | None = None
) -> tuple[int, str, str]:
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
    task = await get_prompt(name="review_agent")
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        model=model,
        agent="review-agent",
        env=env,
    )


async def opencode_merge_agent(target_path: Path, task: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
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
    command = [str(OPENCODE["path"]), "run", "--dir", str(target_path), "--model", model, "--agent", agent]

    if session_id is not None:
        command.extend(["--session", session_id])
    if task_title is not None:
        command.extend(["--title", task_title])

    command.append(shlex.quote(task)[:4095])
    return await run_command(command=command, target_path=target_path, disable_stdio=disable_stdio, env=env)


async def get_opencode_sessions(target_path: Path, env: dict[str, str] | None = None) -> list[dict[str, str]]:
    command = [str(OPENCODE["path"]), "session", "list", "--format", "json"]
    _, result, _ = await run_command(command=command, target_path=target_path, disable_stdio=True, env=env)
    return json.loads(result)


async def get_opencode_session_id(target_path: Path, task_title: str, env: dict[str, str] | None = None) -> str | None:
    sessions = await get_opencode_sessions(target_path=target_path, env=env)
    filtered_sessions = list(filter(lambda x: task_title == x.get("title", ""), sessions))
    if not filtered_sessions:
        print_message("Session not found", style="info")

    fallback_session_id = None
    target_directory = str(target_path).rstrip("/")
    for session in sorted(filtered_sessions, key=lambda x: x["updated"], reverse=True):
        # TODO: Think how to proceed with a worktree mistmatch
        # if not fallback_session_id:
        #     fallback_session_id = session["id"]

        session_directory = session.get("directory", "").rstrip("/")
        if session_directory == target_directory:
            return session["id"]

    print_message("Worktree mistmatch, using fallback session id", style="error")
    return fallback_session_id


async def get_opencode_session_length(
    target_path: Path, session_id: str, env: dict[str, str] | None = None
) -> int | None:
    """Get the total token count for an opencode session via `opencode export`.

    Sums input, output, reasoning, cache.read, and cache.write tokens.
    Returns None if the command fails or the export JSON is malformed.
    """
    command = [str(OPENCODE["path"]), "export", session_id]
    exit_code, result, _ = await run_command(command=command, target_path=target_path, disable_stdio=True, env=env)
    if exit_code != 0:
        return None

    try:
        data = json.loads(result)
    except (json.JSONDecodeError, ValueError):
        return None

    info = data.get("info")
    if not info:
        return None

    tokens = info.get("tokens")
    if not tokens:
        return None

    total = tokens.get("input", 0) or 0
    total += tokens.get("output", 0) or 0
    total += tokens.get("reasoning", 0) or 0
    cache = tokens.get("cache")
    if cache:
        total += cache.get("read", 0) or 0
        total += cache.get("write", 0) or 0

    return total


async def opencode_compact_session(
    target_path: Path, session_id: str, env: dict[str, str] | None = None
) -> tuple[int, str, str]:
    """Run the /compact command within an existing opencode session."""
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
    if (start_index := plan_output.find(PLAN_HEADER_STRING)) != -1:
        plan_output = plan_output[start_index:]

    for end_string in (PLAN_IS_READY_STRING, PLAN_HAS_QUESTIONS):
        if (end_index := plan_output.find(end_string)) != -1:
            plan_output = plan_output[:end_index]
            break

    return plan_output.strip()
