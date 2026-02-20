import asyncio
from pathlib import Path

from demetra.services.utils import live_stream


async def run_command(command: list, target_path: Path) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *command, cwd=target_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    if not process.stdout or not process.stderr:
        process.kill()
        raise AttributeError("stdout/stderr is None")

    result, error = [], []
    await asyncio.gather(live_stream(process.stdout, result=result), live_stream(process.stderr, result=error))

    exit_code = await process.wait()
    return exit_code, "\n".join(result), "\n".join(error)
