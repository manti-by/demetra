import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

from demetra.library.constants import OS_ENV_ALLOWLIST
from demetra.services.runtime.utils import live_stream
from demetra.settings import OS_ENV_PROJECT_OPTINS, SUBPROCESS_TIMEOUT


def filter_os_env(project_id: str | None = None) -> dict[str, str]:
    """Return the host OS environment restricted to the allowlist.

    Only keys in ``OS_ENV_ALLOWLIST`` plus any per-project opt-in keys
    (``OS_ENV_PROJECT_OPTINS``) are forwarded; everything else from the host
    OS is dropped.

    Args:
        project_id: Optional project id whose opt-in tokens are forwarded.

    Returns:
        dict[str, str]: The filtered OS environment.
    """
    allowed_keys = set(OS_ENV_ALLOWLIST)
    if project_id is not None:
        allowed_keys.update(OS_ENV_PROJECT_OPTINS.get(project_id, []))
    return {key: value for key, value in os.environ.items() if key in allowed_keys}


def build_subprocess_env(
    extra: dict[str, str] | None = None,
    *,
    project_id: str | None = None,
    user_environment: dict[str, str] | None = None,
    project_environment: dict[str, str] | None = None,
    target_path: Path | None = None,
) -> dict[str, str]:
    """Build the environment for a subprocess from the three env layers.

    The layers are merged in order OS (allowlisted) → user-shared → project,
    so project overrides user-shared on key conflict. Per-step ``extra``
    overrides sit on top of all three layers. This is the single place where
    the subprocess environment is assembled.

    Args:
        extra: Per-step overrides merged last (highest precedence).
        project_id: Optional project id used for OS env opt-in tokens.
        user_environment: Pre-resolved user-shared env mapping; when omitted
            the OS allowlist layer is used as-is.
        project_environment: Pre-resolved project env mapping.
        target_path: The working directory; sets ``PWD`` when given.

    Returns:
        dict[str, str]: The merged environment.
    """
    merged_env = filter_os_env(project_id=project_id)
    if user_environment is not None:
        merged_env.update(user_environment)
    if project_environment is not None:
        merged_env.update(project_environment)
    if extra:
        merged_env.update(extra)
    if target_path is not None:
        merged_env["PWD"] = str(target_path)
    return merged_env


async def pipe_stdin_input(stdin: asyncio.StreamWriter, text: str) -> None:
    """Write text to a subprocess stdin stream and close it.

    The child may exit before reading stdin, raising BrokenPipeError or
    ConnectionResetError; those are expected and ignored so run_command's
    gather flow still reaches process.wait. The writer is always closed.

    Args:
        stdin: The process stdin stream writer.
        text: The text to pipe to the process.
    """
    try:
        stdin.write(data=text.encode())
        await stdin.drain()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        stdin.close()
    await stdin.wait_closed()


async def run_command(
    command: list,
    target_path: Path,
    disable_stdio: bool = False,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    timeout: int | None = SUBPROCESS_TIMEOUT,
    project_id: str | None = None,
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
        env: Optional per-step environment overrides merged on top of the
            three-layer merged environment.
        input_text: Optional text to pipe to the process on stdin.
        timeout: Timeout in seconds; on expiry the process is killed and exit
            code -1 is returned.
        project_id: Optional project id whose OS opt-ins are merged into the
            subprocess environment.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr.
    """
    merged_env = build_subprocess_env(
        extra=env,
        project_id=project_id,
        target_path=target_path,
    )
    process_kwargs: dict[str, Any] = {
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
                streams.append(pipe_stdin_input(stdin=process.stdin, text=input_text))
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
    project_id: str | None = None,
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
        env: Optional per-step environment overrides merged on top of the
            three-layer merged environment.
        timeout: Timeout in seconds; on expiry the process is killed.
        project_id: Optional project id whose OS opt-ins are merged into the
            subprocess environment.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr.
    """
    merged_env = build_subprocess_env(
        extra=env,
        project_id=project_id,
        target_path=target_path,
    )

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
