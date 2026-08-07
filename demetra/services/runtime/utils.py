import asyncio
import logging
import os
import re
import sys
from collections.abc import Callable
from logging import Formatter, LogRecord
from pathlib import Path
from typing import overload

from demetra.library.exceptions import SettingsError
from demetra.library.types import CockieSamesite


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def ansi_strip(text: str) -> str:
    """Remove ANSI escape sequences from a string.

    Args:
        text: The text to clean.

    Returns:
        str: The text without ANSI escape codes.
    """
    return ANSI_ESCAPE_RE.sub("", text)


class AnsiStrippingFilter(logging.Filter):
    def filter(self, record: LogRecord) -> bool:
        """Strip ANSI escape codes from log records before they are emitted.

        Args:
            record: The log record to filter.

        Returns:
            bool: Always True; the record is always allowed through.
        """
        record.msg = ansi_strip(record.msg)
        return True


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
    """Stream lines from a subprocess stream until EOF.

    Lines are ANSI-stripped, optionally collected and optionally echoed to
    stdout and the stream logger.

    Args:
        stream: The stream reader to consume.
        result: Optional list to append decoded lines to.
        disable_stdio: Whether to suppress live output to stdout.
    """
    while True:
        if not (line := await stream.readline()):
            break

        decoded = ansi_strip(line.decode())
        if result is not None:
            result.append(decoded)

        if not disable_stdio:
            sys.stdout.write(decoded)
            sys.stdout.flush()
            stream_logger.info(decoded.rstrip())


async def log_stream(stream: asyncio.StreamReader, logger_callable: Callable) -> None:
    """Forward lines from a subprocess stream to a logging callable.

    Args:
        stream: The stream reader to consume.
        logger_callable: The callable invoked with each decoded line.
    """
    while True:
        if not (line := await stream.readline()):
            break

        decoded = line.decode()
        logger_callable(decoded)


async def is_package_installed(target_path: Path, package_name: str, env: dict[str, str] | None = None) -> bool:
    """Check whether a package is installed in the project's environment.

    Args:
        target_path: Directory of the project whose environment to query.
        package_name: The package name to look for.
        env: Optional environment overrides for the subprocess.

    Returns:
        bool: True when the package appears in the dependency tree.
    """
    from demetra.services.runtime.subprocess import run_command
    from demetra.settings import UV

    _, result, _ = await run_command(
        command=[str(UV["path"]), "tree", "--quiet", "--package", package_name],
        target_path=target_path,
        disable_stdio=True,
        env=env,
    )
    return result != ""


async def setup_session_logging(task_id: str) -> None:
    """Route logging for a workflow session into its own log file.

    Installs a file handler for the session's log path on the root and stream
    loggers, replacing the previous root file handler to avoid duplication.

    Args:
        task_id: The task identifier used to name the session log file.
    """
    from demetra.settings import LOG_DIR, LOGGING

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
    file_handler.addFilter(AnsiStrippingFilter())

    if root_file_handler is not None:
        root_file_handler.close()
        root_logger.removeHandler(root_file_handler)
    root_logger.addHandler(file_handler)
    stream_logger.addHandler(file_handler)
    file_config["filename"] = str(session_log_path)


def non_negative_int(value: object) -> int | None:
    """Coerce a value to a non-negative int, or None when unsuitable.

    Rejects booleans, non-ints and negative values.

    Args:
        value: The value to coerce.

    Returns:
        int | None: The non-negative int, or None.
    """
    if isinstance(value, bool):
        return None
    if not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def get_cookie_samesite(is_cockie_secure: bool) -> CockieSamesite:
    """Resolve the cookie SameSite value from the environment.

    Validates the ``COOKIE_SAMESITE`` setting and enforces that ``none``
    requires secure cookies.

    Returns:
        CockieSamesite: ``"lax"``, ``"strict"`` or ``"none"``, defaulting to
            ``"lax"`` for unknown values.

    Raises:
        SettingsError: When ``none`` is requested without secure cookies.
    """
    value = os.environ.get("COOKIE_SAMESITE", "lax").lower()
    if value not in {"lax", "strict", "none"}:
        return "lax"
    if value == "none" and not is_cockie_secure:
        raise SettingsError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")
    return value


def env_get_int(name: str, default: int) -> int:
    """Read a nonnegative integer from the environment, falling back on invalid values.

    Args:
        name: The environment variable name.
        default: The fallback value when the variable is unset, not an int,
            or negative.

    Returns:
        int: The parsed value, or the default.
    """
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        pass
    return default


def env_get_bool(name: str, default: bool) -> bool:
    """Read a string boolean from the environment, falling back on invalid values.

    Args:
        name: The environment variable name.
        default: The fallback value when the variable is unset or invalid.

    Returns:
        bool: The parsed value, or the default.
    """
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return default


def env_get_list(name: str, default: list) -> list:
    """Read a string and split into list, falling back on invalid values.

    Args:
        name: The environment variable name.
        default: The fallback value when the variable is unset.

    Returns:
        list: The parsed value, or the default.
    """
    value = os.environ.get(name)
    if value is None:
        return default
    list_value = value.split(",")
    return [x.strip() for x in list_value if x.strip()]


@overload
def env_get_str(name: str, default: str) -> str: ...


@overload
def env_get_str(name: str, default: None) -> str | None: ...


def env_get_str(name: str, default: str | None) -> str | None:
    """Read a string from the environment, falling back on the default.

    Args:
        name: The environment variable name.
        default: The fallback value when the variable is unset.

    Returns:
        str | None: The value, or the default.
    """
    value = os.environ.get(name)
    if value is None:
        return default
    return value


@overload
def env_get_path(name: str, default: Path) -> Path: ...


@overload
def env_get_path(name: str, default: None) -> Path | None: ...


def env_get_path(name: str, default: Path | None) -> Path | None:
    """Read a path from the environment, falling back on the default.

    Args:
        name: The environment variable name.
        default: The fallback value when the variable is unset.

    Returns:
        Path | None: The value, or the default.
    """
    value = os.environ.get(name)
    if value is None:
        return default
    return Path(value).resolve()
