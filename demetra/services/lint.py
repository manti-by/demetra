from pathlib import Path

from demetra.services.subprocess import run_command
from demetra.settings import UV


async def run_ruff_format(target_path: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Auto-format a directory with ruff format.

    Args:
        target_path: Directory to format.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the command.
    """
    return await run_command(
        command=[str(UV["path"]), "run", "--active", "ruff", "format", "--silent"],
        target_path=target_path,
        env=env,
    )


async def run_ruff_checks(target_path: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Run ruff lint checks over a directory.

    Args:
        target_path: Directory to lint.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the command.
    """
    return await run_command(
        command=[str(UV["path"]), "run", "--active", "ruff", "check", "--quiet"],
        target_path=target_path,
        env=env,
    )


async def run_ruff_fix(target_path: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Run ruff lint with automatic fixes enabled.

    Args:
        target_path: Directory to lint and fix.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the command.
    """
    return await run_command(
        command=[str(UV["path"]), "run", "--active", "ruff", "check", "--fix", "--quiet"],
        target_path=target_path,
        env=env,
    )


async def run_ruff_check_diff(target_path: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Compute the ruff diff that would be applied without modifying files.

    Args:
        target_path: Directory to analyze.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the command.
    """
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
