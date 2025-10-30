import asyncio
from pathlib import Path

from chimera.settings import GIT_WORKTREE_PATH


async def setup_git_worktree(project_name: str, project_path: Path, branch_name: str) -> tuple[str, str, Path]:
    call = ["git", "worktree", "add", "-b", branch_name, GIT_WORKTREE_PATH / project_name]
    proc = await asyncio.create_subprocess_exec(
        *call, cwd=project_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode(), stderr.decode(), GIT_WORKTREE_PATH / project_name


async def remove_git_worktree(project_path: Path, worktree_path: Path) -> tuple[str, str]:
    call = ["git", "worktree", "remove", worktree_path]
    proc = await asyncio.create_subprocess_exec(
        *call, cwd=project_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode(), stderr.decode()
