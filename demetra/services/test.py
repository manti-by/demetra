from pathlib import Path

from demetra.services.subprocess import run_command


async def run_pytests(target_path: Path, session_id: str | None = None) -> tuple[int, str, str]:
    return await run_command(command=["uv", "run", "pytest", "--lf", "--quiet", "--color=no"], target_path=target_path)
