import json
import shlex
from pathlib import Path

from demetra.services.subprocess import run_command
from demetra.settings import OPENCODE_MODEL, OPENCODE_PATH


async def plan_agent(
    target_path: Path, task: str, session_id: str | None = None, task_title: str | None = None
) -> tuple[int, str, str]:
    task += (
        "\nIf you have some question about implementation, just print in the end `Please check my questions above.`"
        "\nIf there are no questions, just print in the end `Ready to procceed to build.`"
    )
    return await run_opencode_agent(
        target_path=target_path, task=task, session_id=session_id, task_title=task_title, agent="plan"
    )


async def build_agent(
    target_path: Path, task: str, session_id: str | None = None, task_title: str | None = None
) -> tuple[int, str, str]:
    # Override agents settings in the target repository
    task += "\nDO NOT commit or push any changes, just stage them"
    return await run_opencode_agent(
        target_path=target_path, task=task, session_id=session_id, task_title=task_title, agent="build"
    )


async def run_opencode_agent(
    target_path: Path, task: str, agent: str, session_id: str | None = None, task_title: str | None = None
) -> tuple[int, str, str]:
    command = [str(OPENCODE_PATH), "run", "--model", OPENCODE_MODEL, "--agent", agent]

    if session_id is not None:
        command.extend(["--session", session_id])
    if task_title is not None:
        command.extend(["--title", task_title])

    command.append(shlex.quote(task)[:4095])
    return await run_command(command=command, target_path=target_path)


async def get_opencode_sessions(target_path: Path) -> list[dict[str, str]]:
    command = [str(OPENCODE_PATH), "session", "list", "--format", "json"]
    _, result, _ = await run_command(command=command, target_path=target_path)
    return json.loads(result)


async def get_opencode_session_id(target_path: Path, task_title: str) -> str | None:
    for session in await get_opencode_sessions(target_path=target_path):
        if session["title"] == task_title:
            return session["id"]
    return None
