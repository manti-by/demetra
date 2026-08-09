from pathlib import Path

from demetra.services.runtime.subprocess import run_command
from demetra.settings import CODERABBIT


async def coderabbit_review_agent(target_path: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Run a CodeRabbit review over the uncommitted changes in a directory.

    Args:
        target_path: Directory to run the review in.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the review run.
    """
    return await run_coderabbit_agent(target_path=target_path, env=env)


async def run_coderabbit_agent(target_path: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Invoke the CodeRabbit CLI for a prompt-only review of uncommitted changes.

    Args:
        target_path: Directory to run the review in.
        env: Optional environment overrides for the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the review run.
    """
    command = [str(CODERABBIT["path"]), "review", "--prompt-only", "--no-color", "--type", "uncommitted"]
    return await run_command(command=command, target_path=target_path, env=env)
