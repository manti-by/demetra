import re
from pathlib import Path

from demetra.services.subprocess import run_command
from demetra.settings import GITHUB


_PR_LINK_RE = re.compile(r"https?://[^/\s]+/[^/\s]+/[^/\s]+/pull/\d+")


def extract_pr_link(stdout: str) -> str | None:
    """Extract the PR URL from ``gh pr create`` stdout, if present."""
    match = _PR_LINK_RE.search(stdout)
    return match.group(0) if match else None


async def create_pull_request(
    target_path: Path,
    branch_name: str,
    title: str,
    body: str = "",
    base: str = "master",
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    command = [
        str(GITHUB["path"]),
        "pr",
        "create",
        "--base",
        base,
        "--head",
        branch_name,
        "--title",
        title,
        "--body",
        body,
    ]
    return await run_command(command=command, target_path=target_path, env=env)
