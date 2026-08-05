from pathlib import Path

from demetra.library.exceptions import BuildError
from demetra.services.opencode import opencode_validate_agent
from demetra.services.tui import print_message
from demetra.services.utils import NO_ISSUE_TOKENS_CASE


async def run_validate_agent(target_path: Path, build_plan: str, env: dict[str, str] | None = None) -> str | None:
    """Run the validate agent and return missing plan items, or None on full coverage.

    Invokes the read-only validate agent against the staged diff and the build
    plan, dropping no-issue lines and blank output. An empty result means every
    plan step has a corresponding change in the diff.

    Args:
        target_path: Directory to run the validate agent in.
        build_plan: The finalized build plan to check coverage against.
        env: Optional environment overrides for the subprocess.

    Returns:
        str | None: The numbered missing plan items, or None when the plan is
            fully covered.

    Raises:
        BuildError: When the validate agent exits with a non-zero exit code.
    """
    print_message(message="Running VALIDATE agent", style="heading")

    exit_code, stdout, stderr = await opencode_validate_agent(target_path=target_path, build_plan=build_plan, env=env)
    if exit_code != 0:
        raise BuildError(
            f"Validate agent failed (exit {exit_code}): {stderr.strip() or stdout.strip() or 'unknown error'}"
        )

    parts: list[str] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.casefold() in NO_ISSUE_TOKENS_CASE:
            continue
        parts.append(stripped)
    if not parts:
        print_message(message="All plan steps are covered, continuing the workflow.", style="result")
        return None

    missing_items = "\n".join(parts)
    print_message(message="Validate agent returned missing plan items", style="result")
    print_message(message=missing_items, style="result")
    return missing_items
