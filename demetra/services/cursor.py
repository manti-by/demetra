from pathlib import Path

from demetra.services.prompt import get_prompt
from demetra.services.subprocess import run_command
from demetra.settings import CURSOR


async def cursor_review_agent(target_path: Path, session_id: str | None = None) -> tuple[int, str, str]:
    task = await get_prompt(name="review_agent")
    return await run_cursor_agent(target_path=target_path, task=task, session_id=session_id)


async def run_cursor_agent(target_path: Path, task: str, session_id: str | None = None) -> tuple[int, str, str]:
    command = [str(CURSOR["path"]), "--plan", "--print", task, "--force"]
    if session_id is not None:
        command.extend(["--session", session_id])
    return await run_command(command=command, target_path=target_path)
