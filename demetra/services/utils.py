import asyncio
import logging
import sys
from collections.abc import Callable
from logging import Formatter
from pathlib import Path

from demetra.settings import LOG_DIR, LOGGING


stream_logger = logging.getLogger("demetra.services.subprocess_stream")
stream_logger.propagate = False


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
            stream_logger.info(decoded.rstrip())


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


async def setup_session_logging(task_id: str) -> None:
    session_dir = LOG_DIR if LOG_DIR.name == "sessions" else LOG_DIR / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_log_path = session_dir / f"{task_id}.log"

    root_logger = logging.getLogger()
    file_config = LOGGING["handlers"]["file"]
    root_file_handler = next((h for h in root_logger.handlers if isinstance(h, logging.FileHandler)), None)

    if Path(file_config["filename"]).resolve() == session_log_path.resolve():
        # Root already writes to the session log — adding another handler would
        # duplicate every propagated record. Reuse it for the stream logger.
        if root_file_handler is not None:
            stream_logger.addHandler(root_file_handler)
        return

    formatter_config = LOGGING["formatters"][file_config["formatter"]]
    file_handler = logging.FileHandler(session_log_path)
    file_handler.setLevel(file_config["level"])
    file_handler.setFormatter(Formatter(fmt=formatter_config["format"], datefmt=formatter_config["datefmt"]))

    if root_file_handler is not None:
        root_file_handler.close()
        root_logger.removeHandler(root_file_handler)
    root_logger.addHandler(file_handler)
    stream_logger.addHandler(file_handler)
    file_config["filename"] = str(session_log_path)


def non_negative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value
