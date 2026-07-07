import asyncio
import logging
import sys
from collections.abc import Callable
from logging import Formatter, Logger
from pathlib import Path

from demetra.settings import LOG_DIR, LOGGING


NO_ISSUE_TOKENS = {
    "silent",
    "no output",
    "(no output)",
    "no issues found.",
    "no issues found",
    "no clear, high-severity issues found.",
    "no output - no critical or error-level issues found.",
    "no critical or error-level issues found.",
    "lgtm",
    "looks good.",
    "looks good",
    "all good.",
    "all good",
    "nothing to report.",
    "nothing to report",
}

NO_ISSUE_TOKENS_CASE = {t.casefold() for t in NO_ISSUE_TOKENS}


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


async def is_package_installed(target_path: Path, package_name: str, env: dict[str, str] | None = None) -> bool:
    from demetra.services.subprocess import run_command
    from demetra.settings import UV

    _, result, _ = await run_command(
        command=[str(UV["path"]), "tree", "--quiet", "--package", package_name],
        target_path=target_path,
        disable_stdio=True,
        env=env,
    )
    return result != ""


async def setup_session_logging(logger: Logger, task_id: str) -> None:
    if LOG_DIR.name == "sessions":
        session_dir = LOG_DIR
    else:
        session_dir = LOG_DIR / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_log_path = session_dir / f"{task_id}.log"

    if LOGGING["handlers"]["file"]["filename"] == str(session_log_path):
        return

    formatter_name = LOGGING["handlers"]["file"].get("formatter")
    formatter_config = LOGGING.get("formatters", {}).get(formatter_name, {})
    fmt = Formatter(
        fmt=formatter_config.get("format"),
        datefmt=formatter_config.get("datefmt"),
    )

    file_handler = logging.FileHandler(session_log_path)
    file_handler.setLevel(LOGGING["handlers"]["file"]["level"])
    file_handler.setFormatter(fmt)

    for handler in logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            logger.removeHandler(handler)
    logger.addHandler(file_handler)

    tui_logger = logging.getLogger("demetra.services.tui")
    for handler in tui_logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            tui_logger.removeHandler(handler)
    tui_logger.addHandler(file_handler)


def non_negative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value
