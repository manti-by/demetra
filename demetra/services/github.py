from pathlib import Path

from demetra.services.subprocess import run_command
from demetra.settings import GH_PATH


async def create_pull_request(target_path: Path, branch_name: str, title: str, base: str = "master") -> str:
    command = [GH_PATH, "pr", "create", "--base", base, "--head", branch_name, "--title", title]
    exit_code, stdout, stderr = await run_command(command=command, target_path=target_path)
    if exit_code != 0:
        raise RuntimeError(f"Failed to create PR: {stderr}")
    for line in stdout.strip().split("\n"):
        if "http" in line:
            return line.strip()
    return stdout.strip()
