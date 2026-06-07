from pathlib import Path

from demetra.services.subprocess import run_command
from demetra.settings import CODERABBIT


async def coderabbit_review_agent(target_path: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    return await run_coderabbit_agent(target_path=target_path, env=env)


async def run_coderabbit_agent(target_path: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    command = [str(CODERABBIT["path"]), "review", "--prompt-only", "--no-color", "--type", "uncommitted"]
    return await run_command(command=command, target_path=target_path, env=env)
