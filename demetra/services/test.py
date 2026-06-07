from pathlib import Path

from demetra.services.subprocess import run_command
from demetra.settings import UV


async def run_pytests(
    target_path: Path, session_id: str | None = None, env: dict[str, str] | None = None
) -> tuple[int, str, str]:
    return await run_command(
        command=[str(UV["path"]), "run", "--active", "pytest", "--lf", "--quiet", "--color=no"],
        target_path=target_path,
        env=env,
    )
