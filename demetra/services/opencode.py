import shlex
from pathlib import Path

from demetra.services.subprocess import run_command
from demetra.settings import OPENCODE_MODEL, OPENCODE_PATH


async def plan_agent(session_id: str, target_path: Path, task: str) -> str:
    return await run_opencode_agent(session_id, target_path, task, agent="plan")


async def build_agent(session_id: str, target_path: Path, task: str) -> str:
    # Override agents settings in the target repository
    task += "\nDO NOT commit or push any changes, just stage them"
    return await run_opencode_agent(session_id, target_path, task, agent="build")


async def run_opencode_agent(session_id: str, target_path: Path, task: str, agent: str) -> str:
    command = [OPENCODE_PATH, "run", "--session", session_id, "--model", OPENCODE_MODEL, "--agent", agent]
    command.append(shlex.quote(task))
    return await run_command(command=command, target_path=target_path)
