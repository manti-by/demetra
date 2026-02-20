from pathlib import Path

from demetra.services.subprocess import run_command


async def check_pytest_support(target_path: Path) -> tuple[int, str, str]:
    return await run_command(command=["uv", "tree", "--quiet", "--package", "pytest"], target_path=target_path)


async def run_tests(target_path: Path, session_id: str | None = None) -> tuple[int, str, str]:
    return await run_command(command=["uv", "run", "pytest", "--lf", "--quiet", "--color=no"], target_path=target_path)
