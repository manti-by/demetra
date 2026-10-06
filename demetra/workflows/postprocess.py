from pathlib import Path

from demetra.library.models import SessionEnvironment
from demetra.services.quality.lint import run_ruff_check_diff, run_ruff_fix, run_ruff_format
from demetra.services.runtime.tui import print_message
from demetra.services.runtime.utils import is_package_installed


async def postprocess_with_ruff(
    target_path: Path, environment: SessionEnvironment | None = None
) -> tuple[bool, str | None]:
    """Auto-format and auto-fix a directory with ruff and report remaining issues.

    Runs ruff format and ruff check --fix, then computes the diff of issues
    that could not be fixed automatically.

    Args:
        target_path: Directory to post-process.
        environment: The resolved session environment forwarded to the subprocess.

    Returns:
        tuple[bool, str | None]: Whether unresolved ruff issues remain, and
            the diff feedback when they do.
    """
    if not await is_package_installed(target_path=target_path, package_name="ruff", environment=environment):
        return False, None

    print_message("Running RUFF post-processor", style="heading")

    await run_ruff_format(target_path=target_path, environment=environment)
    await run_ruff_fix(target_path=target_path, environment=environment)

    ruff_exit_code, ruff_feedback, _ = await run_ruff_check_diff(target_path=target_path, environment=environment)

    if ruff_exit_code:
        print_message("RUFF: unresolved issues for agent", style="result")
        return True, ruff_feedback

    print_message("RUFF: clean", style="result")
    return False, None
