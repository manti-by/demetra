from pathlib import Path

from demetra.services.subprocess import run_command


async def run_ty_checks(target_path: Path, session_id: str | None = None) -> tuple[int, str, str]:
    return await run_command(command=["uvx", "ty", "check"], target_path=target_path)


async def run_ruff_checks(target_path: Path, session_id: str | None = None) -> tuple[int, str, str]:
    return await run_command(
        command=["uvx", "ruff", "check", "--fix", "--exit-non-zero-on-fix"], target_path=target_path
    )
