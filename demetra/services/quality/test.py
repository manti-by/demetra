from pathlib import Path

from demetra.library.models import SessionEnvironment
from demetra.services.runtime.subprocess import run_command
from demetra.settings import UV


async def run_pytests(
    target_path: Path,
    session_id: str | None = None,
    environment: SessionEnvironment | None = None,
    *,
    full_suite: bool = False,
) -> tuple[int, str, str]:
    """Run pytest over a project directory.

    Last-failed mode is the default so callers can recheck only the tests that
    failed previously. With ``full_suite=True`` the whole suite runs, catching
    regressions in tests that passed on an earlier run.

    Args:
        target_path: Directory to run pytest in.
        session_id: Reserved for compatibility; not used by the command.
        environment: The resolved session environment forwarded to the subprocess.
        full_suite: Run the whole suite instead of only the last failures.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    command = [str(UV["path"]), "run", "--active", "pytest"]
    if not full_suite:
        command.append("--lf")
    command.extend(["--quiet", "--color=no"])
    return await run_command(
        command=command,
        target_path=target_path,
        environment=environment,
    )
