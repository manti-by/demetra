from pathlib import Path

from demetra.services.subprocess import run_command
from demetra.settings import UV


async def run_ruff_format(target_path: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    return await run_command(
        command=[str(UV["path"]), "run", "--active", "ruff", "format", "--silent"],
        target_path=target_path,
        env=env,
    )


async def run_ruff_checks(target_path: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    return await run_command(
        command=[str(UV["path"]), "run", "--active", "ruff", "check", "--quiet"],
        target_path=target_path,
        env=env,
    )


async def run_ruff_fix(target_path: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    return await run_command(
        command=[str(UV["path"]), "run", "--active", "ruff", "check", "--fix", "--quiet"],
        target_path=target_path,
        env=env,
    )


async def run_ruff_check_diff(target_path: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    return await run_command(
        command=[
            str(UV["path"]),
            "run",
            "--active",
            "ruff",
            "check",
            "--diff",
            "--output-format=concise",
        ],
        target_path=target_path,
        env=env,
    )
