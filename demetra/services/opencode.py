import shlex
from pathlib import Path

from demetra.services.subprocess import run_command
from demetra.settings import OPENCODE_MODEL, OPENCODE_PATH


async def plan_agent(target_path: Path, task: str, repeat: bool = False) -> str:
    return await run_opencode_agent(target_path, task, repeat=repeat, agent="plan")


async def build_agent(target_path: Path, task: str, repeat: bool = False) -> str:
    # Override agents settings in the target repository
    task += "\nDO NOT commit or push any changes, just stage them"
    return await run_opencode_agent(target_path, task, repeat=repeat, agent="build")


async def run_opencode_agent(target_path: Path, task: str, repeat: bool = False, agent: str = "plan") -> str:
    command = [OPENCODE_PATH, "run", "--model", OPENCODE_MODEL, "--agent", agent]
    if repeat:
        command.append("--continue")
    command.append(shlex.quote(task))
    return await run_command(command=command, target_path=target_path)
