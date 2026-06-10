import asyncio
import os
from pathlib import Path

from demetra.services.utils import live_stream
from demetra.settings import SUBPROCESS_TIMEOUT


async def run_command(
    command: list,
    target_path: Path,
    disable_stdio: bool = False,
    env: dict[str, str] | None = None,
    timeout: int | None = SUBPROCESS_TIMEOUT,
) -> tuple[int, str, str]:
    # TODO: MNT-111 - Process environment
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    merged_env["PWD"] = str(target_path)
    process = await asyncio.create_subprocess_exec(
        *command, cwd=target_path, env=merged_env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    if not process.stdout or not process.stderr:
        process.kill()
        raise AttributeError("stdout/stderr is None")

    result, error = [], []
    try:
        async with asyncio.timeout(timeout):
            await asyncio.gather(
                live_stream(process.stdout, result=result, disable_stdio=disable_stdio),
                live_stream(process.stderr, result=error, disable_stdio=disable_stdio),
            )

            exit_code = await process.wait()
    except TimeoutError:
        process.kill()
        await process.wait()
        exit_code = -1
        error.append("Command timed out\n")

    return exit_code, "\n".join(result) if result else "", "\n".join(error) if error else ""
