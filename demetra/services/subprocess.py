import asyncio
import os
import tempfile
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


async def run_command_to_file(
    command: list,
    target_path: Path,
    disable_stdio: bool = False,
    env: dict[str, str] | None = None,
    timeout: int | None = SUBPROCESS_TIMEOUT,
) -> tuple[int, str, str]:
    """Run command with stdout redirected to a temp file, then read it back.

    Necessary for subprocesses (e.g. `opencode export`) that truncate output to the
    OS pipe buffer (64KB) when stdout is a PIPE instead of a regular file or TTY.
    Behaves like `run_command` but redirects stdout to a temp file, reads it back
    after the process exits, and deletes the file.
    """
    # TODO: MNT-111 - Process environment
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    merged_env["PWD"] = str(target_path)

    tmp = tempfile.NamedTemporaryFile(mode="w+b", delete=False)
    tmp.close()
    tmp_path = Path(tmp.name)
    try:
        with tmp_path.open("w+b") as stdout_file:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=target_path,
                env=merged_env,
                stdout=stdout_file,
                stderr=asyncio.subprocess.PIPE,
            )
            if not process.stderr:
                process.kill()
                raise AttributeError("stderr is None")

            error: list[str] = []
            try:
                async with asyncio.timeout(timeout):
                    await live_stream(process.stderr, result=error, disable_stdio=disable_stdio)
                    exit_code = await process.wait()
            except TimeoutError:
                process.kill()
                await process.wait()
                exit_code = -1
                error.append("Command timed out\n")

        stdout_data = tmp_path.read_bytes().decode(errors="replace")
    finally:
        tmp_path.unlink(missing_ok=True)

    return exit_code, stdout_data, "\n".join(error) if error else ""
