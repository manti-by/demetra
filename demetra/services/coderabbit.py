from pathlib import Path

from demetra.services.subprocess import run_command
from demetra.settings import CODERABBIT_PATH


async def review_agent(target_path: Path) -> tuple[int, str, str]:
    return await run_coderabbit_agent(target_path=target_path)


async def run_coderabbit_agent(target_path: Path) -> tuple[int, str, str]:
    command = [str(CODERABBIT_PATH), "review", "--prompt-only", "--no-color", "--type", "uncommitted"]
    return await run_command(command=command, target_path=target_path)
