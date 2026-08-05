import asyncio
import os
import tempfile
from pathlib import Path

from demetra.services.utils import live_stream
from demetra.settings import SUBPROCESS_TIMEOUT


async def pipe_stdin_input(stdin: asyncio.StreamWriter, text: str) -> None:
    """Write text to a subprocess stdin stream and close it.

    Args:
        stdin: The process stdin stream writer.
        text: The text to pipe to the process.
    """
    stdin.write(text.encode())
    await stdin.drain()
    stdin.close()


async def run_command(
    command: list,
    target_path: Path,
    disable_stdio: bool = False,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    timeout: int | None = SUBPROCESS_TIMEOUT,
) -> tuple[int, str, str]:
    """Run a command as a subprocess and capture its output.

    Streams stdout and stderr while the process runs, optionally suppressing
    live output, and returns the exit code and captured streams. When
    ``input_text`` is given it is piped to the process on stdin, which lets
    callers deliver large payloads (e.g. prompts) without command-line length
    limits.

    Args:
        command: The command to run as a list of arguments.
        target_path: The working directory for the process.
        disable_stdio: Whether to suppress live output to stdout.
        env: Optional environment overrides merged over the current env.
        input_text: Optional text to pipe to the process on stdin.
        timeout: Timeout in seconds; on expiry the process is killed and exit
            code -1 is returned.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr.
    """
    # TODO: MNT-111 - Process environment
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    merged_env["PWD"] = str(target_path)
    process_kwargs: dict = {
        "cwd": target_path,
        "env": merged_env,
        "stdout": asyncio.subprocess.PIPE,
        "stderr": asyncio.subprocess.PIPE,
    }
    if input_text is not None:
        process_kwargs["stdin"] = asyncio.subprocess.PIPE
    process = await asyncio.create_subprocess_exec(*command, **process_kwargs)
    if not process.stdout or not process.stderr:
        process.kill()
        raise AttributeError("stdout/stderr is None")

    result, error = [], []
    try:
        async with asyncio.timeout(timeout):
            streams = [
                live_stream(process.stdout, result=result, disable_stdio=disable_stdio),
                live_stream(process.stderr, result=error, disable_stdio=disable_stdio),
            ]
            if input_text is not None:
                if process.stdin is None:
                    process.kill()
                    raise AttributeError("stdin is None")
                streams.append(pipe_stdin_input(process.stdin, input_text))
            await asyncio.gather(*streams)

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
    """Run a command with stdout redirected to a temp file, then read it back.

    Necessary for subprocesses (e.g. ``opencode export``) that truncate output
    to the OS pipe buffer (64KB) when stdout is a PIPE instead of a regular
    file or TTY. Behaves like ``run_command`` but redirects stdout to a temp
    file, reads it back after the process exits, and deletes the file.

    Args:
        command: The command to run as a list of arguments.
        target_path: The working directory for the process.
        disable_stdio: Whether to suppress live stderr output.
        env: Optional environment overrides merged over the current env.
        timeout: Timeout in seconds; on expiry the process is killed.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr.
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
