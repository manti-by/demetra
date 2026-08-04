from pathlib import Path

from demetra.services.subprocess import run_command
from demetra.settings import UV


async def run_pytests(
    target_path: Path, session_id: str | None = None, env: dict[str, str] | None = None
) -> tuple[int, str, str]:
    """Run pytest in last-failed mode over a project directory.

    Args:
        target_path: Directory to run pytest in.
        session_id: Reserved for compatibility; not used by the command.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    return await run_command(
        command=[str(UV["path"]), "run", "--active", "pytest", "--lf", "--quiet", "--color=no"],
        target_path=target_path,
        env=env,
    )
