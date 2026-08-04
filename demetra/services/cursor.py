from pathlib import Path

from demetra.services.prompt import get_prompt
from demetra.services.subprocess import run_command
from demetra.settings import CURSOR


async def cursor_review_agent(target_path: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Run a Cursor review agent over a directory using the review prompt.

    Args:
        target_path: Directory to run the review in.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the review run.
    """
    task = await get_prompt(name="review_agent")
    return await run_cursor_agent(target_path=target_path, task=task, env=env)


async def run_cursor_agent(
    target_path: Path, task: str, session_id: str | None = None, env: dict[str, str] | None = None
) -> tuple[int, str, str]:
    """Invoke the Cursor CLI in plan mode with a given task prompt.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt to pass to the agent.
        session_id: Optional session id to continue an existing session.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    command = [str(CURSOR["path"]), "--plan", "--print", task, "--force"]
    if session_id is not None:
        command.extend(["--session", session_id])
    return await run_command(command=command, target_path=target_path, env=env)
