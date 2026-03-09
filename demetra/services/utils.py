import asyncio
import logging
import sys
from collections.abc import Callable
from logging import Logger
from pathlib import Path

from demetra.settings import LINEAR, LOG_DIR, LOGGING


async def live_stream(
    stream: asyncio.StreamReader, result: list[str] | None = None, disable_stdio: bool = False
) -> None:
    while True:
        if not (line := await stream.readline()):
            break

        decoded = line.decode()
        if result is not None:
            result.append(decoded)

        if not disable_stdio:
            sys.stdout.write(decoded)
            sys.stdout.flush()


async def log_stream(stream: asyncio.StreamReader, logger_callable: Callable) -> None:
    while True:
        if not (line := await stream.readline()):
            break

        decoded = line.decode()
        logger_callable(decoded)


async def is_package_installed(target_path: Path, package_name: str) -> bool:
    from demetra.services.subprocess import run_command

    _, result, _ = await run_command(
        command=["uv", "tree", "--quiet", "--package", package_name],
        target_path=target_path,
        disable_stdio=True,
    )
    return result != ""


async def get_project_id_by_name(name: str) -> str | None:
    return {
        "odin": LINEAR["projects"]["odin"],
        "demetra": LINEAR["projects"]["demetra"],
        "coruscant": LINEAR["projects"]["coruscant"],
    }.get(name.strip().lower())


async def setup_session_logging(logger: Logger, task_id: str) -> None:
    session_log_path = str(LOG_DIR / f"sessions/{task_id}.log")
    if LOGGING["handlers"]["file"]["filename"] == session_log_path:
        return

    file_handler = logging.FileHandler(session_log_path)
    file_handler.setLevel(LOGGING["handlers"]["file"]["level"])
    file_handler.setFormatter(LOGGING["handlers"]["file"]["formatter"])

    logger.handlers.clear()
    logger.addHandler(file_handler)
