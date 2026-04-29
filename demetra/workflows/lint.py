from pathlib import Path

from demetra.services.lint import run_ruff_checks, run_ruff_format
from demetra.services.test import run_pytests
from demetra.services.tui import print_message
from demetra.services.utils import is_package_installed


async def run_lint_and_test(target_path: Path, session_id: str | None = None) -> tuple[bool, str | None]:
    if await is_package_installed(target_path=target_path, package_name="ruff"):
        print_message("Running RUFF linter", style="heading")
        await run_ruff_format(target_path=target_path, session_id=session_id)

        ruff_exit_code, ruff_result, _ = await run_ruff_checks(target_path=target_path, session_id=session_id)
        if ruff_exit_code:
            print_message("Processing RUFF comments", style="result")
            print_message(ruff_result, style="info")
            return True, ruff_result

    if await is_package_installed(target_path=target_path, package_name="pytest"):
        print_message("Running PYTESTs", style="heading")
        pytest_exit_code, pytest_result, _ = await run_pytests(target_path=target_path, session_id=session_id)
        if pytest_exit_code:
            print_message("Processing PYTEST errors", style="result")
            print_message(pytest_result, style="info")
            return True, pytest_result

    return False, None
