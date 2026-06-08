import asyncio
import os
from pathlib import Path

from demetra.services.utils import live_stream


async def run_command(
    command: list, target_path: Path, disable_stdio: bool = False, env: dict[str, str] | None = None
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
    await asyncio.gather(
        live_stream(process.stdout, result=result, disable_stdio=disable_stdio),
        live_stream(process.stderr, result=error, disable_stdio=disable_stdio),
    )

    exit_code = await process.wait()
    return exit_code, "\n".join(result) if result else "", "\n".join(error) if error else ""
