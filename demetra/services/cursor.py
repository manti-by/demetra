from pathlib import Path

from demetra.services.subprocess import run_command
from demetra.settings import CURSOR_PATH


async def review_agent(target_path: Path) -> str:
    task = """
        1. Check git staged changes in the current directory
        2. Review diff and flag only clear, high-severity issues
        3. Leave very short inline comments (1-2 sentences) on changed lines only
        4. Leave a brief summary at the end if any issues were found
        NOTE: Do not write anything if there are no issues found, just exit
    """
    return await run_cursor_agent(target_path=target_path, task=task)


async def run_cursor_agent(target_path: Path, task: str) -> str:
    command = [CURSOR_PATH, "--plan", "--print", task, "--force"]
    return await run_command(command=command, target_path=target_path)
