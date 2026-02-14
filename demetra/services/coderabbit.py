import asyncio
from pathlib import Path

from demetra.settings import CODERABBIT_PATH


async def review_agent(target_path: Path) -> tuple[str, str]:
    return await run_coderabbit_agent(target_path=target_path)


async def run_coderabbit_agent(target_path: Path) -> tuple[str, str]:
    call = [CODERABBIT_PATH, "review", "--prompt-only", "--no-color", "--type", "uncommitted"]
    proc = await asyncio.create_subprocess_exec(
        *call, cwd=target_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode(), stderr.decode()
