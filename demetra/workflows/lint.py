from pathlib import Path

from demetra.services.persistence.database import update_session_step
from demetra.services.quality.lint import run_ruff_checks, run_ruff_format
from demetra.services.quality.test import run_pytests
from demetra.services.runtime.tui import print_message
from demetra.services.runtime.utils import is_package_installed
from demetra.settings import FEATURES


async def run_lint_and_test(
    target_path: Path, session_id: str | None = None, task_id: str | None = None, env: dict[str, str] | None = None
) -> tuple[bool, str | None]:
    """Run the optional ruff and pytest steps over a project directory.

    Ruff and pytest only run when the package is installed and the matching
    feature flag is enabled. The first failing step returns its output as
    feedback for the build agent.

    Args:
        target_path: Directory to lint and test.
        session_id: Reserved; not used by the commands.
        task_id: Optional task id used to update the session step.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[bool, str | None]: Whether a step failed, and the failure
            output when one did.
    """
    if (
        await is_package_installed(target_path=target_path, package_name="ruff", env=env)
        and FEATURES["is_ruff_enabled"]
    ):
        print_message("Running RUFF linter", style="heading")
        if task_id:
            await update_session_step(task_id=task_id, step="lint")

        await run_ruff_format(target_path=target_path, env=env)
        ruff_exit_code, ruff_result, _ = await run_ruff_checks(target_path=target_path, env=env)
        if ruff_exit_code:
            print_message("Processing RUFF comments", style="result")
            print_message(ruff_result, style="info")
            if task_id:
                await update_session_step(task_id=task_id, step="lint")
            return True, ruff_result

    if (
        await is_package_installed(target_path=target_path, package_name="pytest", env=env)
        and FEATURES["is_pytest_enabled"]
    ):
        print_message("Running PYTESTs", style="heading")
        if task_id:
            await update_session_step(task_id=task_id, step="test")

        pytest_exit_code, pytest_result, _ = await run_pytests(target_path=target_path, session_id=session_id, env=env)
        if pytest_exit_code:
            print_message("Processing PYTEST errors", style="result")
            print_message(pytest_result, style="info")
            if task_id:
                await update_session_step(task_id=task_id, step="lint")
            return True, pytest_result

    if task_id:
        await update_session_step(task_id=task_id, step="lint")
    return False, None
