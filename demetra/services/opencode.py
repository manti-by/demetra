import json
import shlex
from pathlib import Path

from demetra.services.prompt import get_prompt
from demetra.services.subprocess import run_command
from demetra.settings import OPENCODE


PLAN_HEADER_STRING = "## Implementation Plan"
PLAN_IS_READY_STRING = "Ready to proceed to build."
PLAN_HAS_QUESTIONS = "Please check my questions above."


async def opencode_plan_agent(target_path: Path, task: str, task_title: str | None = None) -> tuple[int, str, str]:
    task += (
        f"\nIMPORTANT:"
        f"\n- If you have some question about implementation, just print in the end `{PLAN_HAS_QUESTIONS}`"
        f"\n- If there are no questions, just print in the end `{PLAN_IS_READY_STRING}`"
    )

    return await run_opencode_agent(
        target_path=target_path, task=task, task_title=task_title, model=OPENCODE["plan_model"], agent="plan"
    )


async def opencode_build_agent(
    target_path: Path, task: str, session_id: str | None = None, task_title: str | None = None
) -> tuple[int, str, str]:
    task += "\nDO NOT commit or push any changes, just stage them"
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        session_id=session_id,
        task_title=task_title,
        model=OPENCODE["build_model"],
        agent="build",
    )


async def opencode_review_agent(target_path: Path, model: str, task_title: str | None = None) -> tuple[int, str, str]:
    task = await get_prompt(name="review_agent")
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        model=model,
        agent="review",
        disable_stdio=True,
    )


async def run_opencode_agent(
    target_path: Path,
    task: str,
    model: str,
    agent: str,
    session_id: str | None = None,
    task_title: str | None = None,
    disable_stdio: bool = False,
) -> tuple[int, str, str]:
    command = [str(OPENCODE["path"]), "run", "--model", model, "--agent", agent]

    if session_id is not None:
        command.extend(["--session", session_id])
    if task_title is not None:
        command.extend(["--title", task_title])

    command.append(shlex.quote(task)[:4095])
    return await run_command(command=command, target_path=target_path, disable_stdio=disable_stdio)


async def get_opencode_sessions(target_path: Path) -> list[dict[str, str]]:
    command = [str(OPENCODE["path"]), "session", "list", "--format", "json"]
    _, result, _ = await run_command(command=command, target_path=target_path, disable_stdio=True)
    return json.loads(result)


async def get_opencode_session_id(target_path: Path, task_title: str) -> str | None:
    sessions = await get_opencode_sessions(target_path=target_path)
    target_directory = str(target_path).rstrip("/")

    fallback_session_id = None
    for session in sorted(sessions, key=lambda x: x["updated"], reverse=True):
        session_title = session.get("title", "")
        session_directory = session.get("directory", "").rstrip("/")

        if session_directory != target_directory:
            print(f"Skipping session math for {session_directory} and {target_directory}")
            continue

        # Worktree mistmatch
        elif session_title == task_title and not fallback_session_id:
            fallback_session_id = session["id"]

        if session_title == task_title:
            return session["id"]

    return fallback_session_id


async def extract_plan(plan_output: str) -> str:
    if (start_index := plan_output.find(PLAN_HEADER_STRING)) != -1:
        plan_output = plan_output[start_index:]

    for end_string in (PLAN_IS_READY_STRING, PLAN_HAS_QUESTIONS):
        if (end_index := plan_output.find(end_string)) != -1:
            plan_output = plan_output[:end_index]
            break

    return plan_output.strip()
