from pathlib import Path

from demetra.services.subprocess import run_command


async def run_ruff_format(target_path: Path, session_id: str | None = None) -> tuple[int, str, str]:
    return await run_command(command=["uv", "run", "--active", "ruff", "format", "--silent"], target_path=target_path)


async def run_ruff_checks(target_path: Path, session_id: str | None = None) -> tuple[int, str, str]:
    return await run_command(command=["uv", "run", "--active", "ruff", "check", "--quiet"], target_path=target_path)
