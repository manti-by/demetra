from pathlib import Path

from demetra.services.subprocess import run_command
from demetra.settings import GH_PATH


async def create_pull_request(
    target_path: Path, branch_name: str, title: str, base: str = "master"
) -> tuple[int, str, str]:
    command = [str(GH_PATH), "pr", "create", "--base", base, "--head", branch_name, "--title", title, "--body", ""]
    return await run_command(command=command, target_path=target_path)
