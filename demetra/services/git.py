import asyncio
from pathlib import Path

from demetra.settings import GIT_PATH, GIT_WORKTREE_PATH


async def git_worktree_create(target_path: Path, branch_name: str) -> tuple[str, str, Path]:
    worktree_path = GIT_WORKTREE_PATH / branch_name
    call = [GIT_PATH, "worktree", "add", "-b", branch_name, worktree_path]
    process = await asyncio.create_subprocess_exec(
        *call, cwd=target_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode(), stderr.decode(), worktree_path


async def git_commit_and_push(target_path: Path, message: str) -> tuple[str, str, str, str]:
    process = await asyncio.create_subprocess_exec(
        GIT_PATH,
        "commit",
        "-m",
        message,
        cwd=target_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    commit_stdout, commit_stderr = await process.communicate()

    process = await asyncio.create_subprocess_exec(
        GIT_PATH, "push", cwd=target_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    push_stdout, push_stderr = await process.communicate()

    return commit_stdout.decode(), commit_stderr.decode(), push_stdout.decode(), push_stderr.decode()


async def git_worktree_remove(target_path: Path, worktree_path: Path) -> tuple[str, str]:
    call = [GIT_PATH, "worktree", "remove", worktree_path]
    process = await asyncio.create_subprocess_exec(
        *call, cwd=target_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode(), stderr.decode()
