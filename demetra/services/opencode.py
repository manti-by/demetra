import asyncio
import shlex
import sys
from pathlib import Path

from demetra.services.utils import live_stream
from demetra.settings import OPENCODE_MODEL, OPENCODE_PATH


async def plan_agent(target_path: Path, task: str, repeat: bool = False) -> str:
    return await run_opencode_agent(target_path, task, repeat=repeat, agent="plan")


async def build_agent(target_path: Path, task: str, repeat: bool = False) -> str:
    return await run_opencode_agent(target_path, task, repeat=repeat, agent="build")


async def run_opencode_agent(target_path: Path, task: str, repeat: bool = False, agent: str = "plan") -> str:
    call = [OPENCODE_PATH, "run", "--model", OPENCODE_MODEL, "--agent", agent]
    if repeat:
        call.append("--continue")
    call.append(shlex.quote(task))

    process = await asyncio.create_subprocess_exec(
        *call, cwd=target_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    if not process.stdout or not process.stderr:
        process.kill()
        raise AttributeError("stdout/stderr is None")

    result = []
    await asyncio.gather(
        live_stream(process.stdout, sys.stdout),
        live_stream(process.stderr, sys.stderr, result=result),
    )
    await process.wait()
    return "".join(result)
