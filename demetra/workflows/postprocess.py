from pathlib import Path

from demetra.services.lint import run_ruff_check_diff, run_ruff_fix, run_ruff_format
from demetra.services.tui import print_message
from demetra.services.utils import is_package_installed


async def postprocess_with_ruff(target_path: Path) -> tuple[bool, str | None]:
    if not await is_package_installed(target_path=target_path, package_name="ruff"):
        return False, None

    print_message("Running RUFF post-processor", style="heading")

    await run_ruff_format(target_path=target_path)
    await run_ruff_fix(target_path=target_path)

    ruff_exit_code, ruff_feedback, _ = await run_ruff_check_diff(target_path=target_path)

    if ruff_exit_code:
        print_message("RUFF: unresolved issues for agent", style="result")
        return True, ruff_feedback

    print_message("RUFF: clean", style="result")
    return False, None
