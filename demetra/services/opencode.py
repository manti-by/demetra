import asyncio
import shlex
from pathlib import Path

from demetra.settings import OPENCODE_PATH


async def plan_agent(target_path: Path, task: str, repeat: bool = False) -> tuple[str, str]:
    return await run_opencode_agent(target_path, task, repeat=repeat, agent="plan")


async def build_agent(target_path: Path, task: str, repeat: bool = False) -> tuple[str, str]:
    return await run_opencode_agent(target_path, task, repeat=repeat, agent="build")


async def run_opencode_agent(
    target_path: Path, task: str, repeat: bool = False, agent: str = "plan"
) -> tuple[str, str]:
    call = [OPENCODE_PATH, "run", "--agent", agent, "--model", "opencode/minimax-m2.5-free"]
    if repeat:
        call.append("--continue")
    call.append(shlex.quote(task))

    proc = await asyncio.create_subprocess_exec(
        *call, cwd=target_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode(), stderr.decode()
