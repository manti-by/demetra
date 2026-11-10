from pathlib import Path

from demetra.library.exceptions import LintError
from demetra.library.models import SessionEnvironment
from demetra.services.llm.openrouter import ErrorSource, extract_errors
from demetra.services.persistence.database import record_session_step, update_session_step
from demetra.services.quality.lint import run_ruff_checks, run_ruff_format
from demetra.services.quality.test import run_pytests
from demetra.services.runtime.tui import print_message
from demetra.services.runtime.utils import is_package_installed
from demetra.settings import FEATURES


async def _extract_errors(
    raw_output: str,
    *,
    source: ErrorSource,
    task_id: str | None,
    environment: SessionEnvironment | None,
) -> str:
    """Return the cleaned errors for the build agent, or the raw output.

    The extraction never hides the failures: when the LLM call fails or
    returns nothing, the raw tool output is passed through unchanged.

    Args:
        raw_output: The raw ruff or pytest output.
        source: The tool that produced the output, ``ruff`` or ``pytest``.
        task_id: Optional task id used to record the LLM call in the session history.
        environment: The resolved session environment forwarded to the LLM.

    Returns:
        str: The numbered error list, or the raw output when extraction failed.
    """
    try:
        findings = await extract_errors(
            errors_output=raw_output, source=source, task_id=task_id, environment=environment
        )
    except LintError:
        print_message("Failed to extract the errors, sending the raw output to the build agent.", style="warning")
        return raw_output

    if not findings:
        return raw_output
    return "\n".join(f"{i + 1}. {finding}" for i, finding in enumerate(findings))


async def run_lint_and_test(
    target_path: Path,
    *,
    session_id: str | None = None,
    task_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[bool, str | None]:
    """Run the optional ruff and pytest steps over a project directory.

    Ruff and pytest only run when the package is installed and the matching
    feature flag is enabled. The first failing step returns its extracted
    errors as feedback for the build agent.

    Args:
        target_path: Directory to lint and test.
        session_id: Optional opencode session id forwarded to the pytest runner.
        task_id: Optional task id used to advance the session step, record the
            lint/test history rows and record the error-extraction LLM call.
        environment: The resolved session environment forwarded to the subprocess
            and to the error-extraction LLM call.

    Returns:
        tuple[bool, str | None]: Whether a step failed, and the failure
            output when one did.
    """
    if (
        await is_package_installed(target_path=target_path, package_name="ruff", environment=environment)
        and FEATURES["is_ruff_enabled"]
    ):
        print_message("Running RUFF linter", style="heading")
        if task_id:
            await update_session_step(task_id=task_id, step="lint")
            await record_session_step(task_id=task_id, step="lint", repeat=True)

        await run_ruff_format(target_path=target_path, environment=environment)
        ruff_exit_code, ruff_result, _ = await run_ruff_checks(target_path=target_path, environment=environment)
        if ruff_exit_code:
            print_message("Processing RUFF comments", style="result")
            errors = await _extract_errors(ruff_result, source="ruff", task_id=task_id, environment=environment)
            print_message(errors, style="info")
            if task_id:
                await update_session_step(task_id=task_id, step="lint")
            return True, errors

    if (
        await is_package_installed(target_path=target_path, package_name="pytest", environment=environment)
        and FEATURES["is_pytest_enabled"]
    ):
        print_message("Running PYTESTs", style="heading")
        if task_id:
            await update_session_step(task_id=task_id, step="test")
            await record_session_step(task_id=task_id, step="test", repeat=True)

        pytest_exit_code, pytest_result, _ = await run_pytests(
            target_path=target_path, session_id=session_id, environment=environment
        )
        if pytest_exit_code:
            print_message("Processing PYTEST errors", style="result")
            errors = await _extract_errors(pytest_result, source="pytest", task_id=task_id, environment=environment)
            print_message(errors, style="info")
            if task_id:
                await update_session_step(task_id=task_id, step="lint")
            return True, errors

    if task_id:
        await update_session_step(task_id=task_id, step="lint")
    return False, None
