import asyncio
from pathlib import Path

from demetra.settings import OPENCODE_PATH


async def plan_agent(project_path: Path, task: str) -> tuple[str, str]:
    return await run_opencode_agent(project_path, task, agent="plan")


async def build_agent(project_path: Path, task: str) -> tuple[str, str]:
    return await run_opencode_agent(project_path, task, agent="build")


async def run_opencode_agent(project_path: Path, task: str, agent: str = "plan") -> tuple[str, str]:
    task = task + "\nFollow the instructions in the AGENTS.md for Git and Linear workflows."
    call = [OPENCODE_PATH, "run", "--agent", agent, "--model", "opencode/minimax-m2.5-free", f"'{task}'"]
    proc = await asyncio.create_subprocess_exec(
        *call, cwd=project_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode(), stderr.decode()
