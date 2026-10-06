from pathlib import Path

from demetra.library.models import SessionEnvironment
from demetra.services.runtime.subprocess import run_command
from demetra.settings import UV


async def run_pytests(
    target_path: Path, session_id: str | None = None, environment: SessionEnvironment | None = None
) -> tuple[int, str, str]:
    """Run pytest in last-failed mode over a project directory.

    Args:
        target_path: Directory to run pytest in.
        session_id: Reserved for compatibility; not used by the command.
        environment: The resolved session environment forwarded to the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    return await run_command(
        command=[str(UV["path"]), "run", "--active", "pytest", "--lf", "--quiet", "--color=no"],
        target_path=target_path,
        environment=environment,
    )
