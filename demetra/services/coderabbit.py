import asyncio
from pathlib import Path

from demetra.services.utils import live_stream
from demetra.settings import CODERABBIT_PATH


async def review_agent(target_path: Path) -> str:
    return await run_coderabbit_agent(target_path=target_path)


async def run_coderabbit_agent(target_path: Path) -> str:
    call = [CODERABBIT_PATH, "review", "--prompt-only", "--no-color", "--type", "uncommitted"]
    process = await asyncio.create_subprocess_exec(
        *call, cwd=target_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    if not process.stdout or not process.stderr:
        process.kill()
        raise AttributeError("stdout/stderr is None")

    result = []
    await asyncio.gather(live_stream(process.stdout, result=result), live_stream(process.stderr))
    await process.wait()
    return "".join(result)
