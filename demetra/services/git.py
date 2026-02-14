import asyncio
import sys
from pathlib import Path

from demetra.services.utils import live_stream
from demetra.settings import GIT_PATH, GIT_WORKTREE_PATH


async def git_worktree_create(target_path: Path, branch_name: str) -> Path:
    worktree_path = GIT_WORKTREE_PATH / branch_name
    call = [GIT_PATH, "worktree", "add", "-b", branch_name, worktree_path]
    process = await asyncio.create_subprocess_exec(
        *call, cwd=target_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    if not process.stdout or not process.stderr:
        process.kill()
        raise AttributeError("stdout/stderr is None")

    await asyncio.gather(
        live_stream(process.stdout, sys.stdout),
        live_stream(process.stderr, sys.stderr),
    )

    return worktree_path


async def git_worktree_remove(target_path: Path, worktree_path: Path):
    call = [GIT_PATH, "worktree", "remove", worktree_path]
    process = await asyncio.create_subprocess_exec(
        *call, cwd=target_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    if not process.stdout or not process.stderr:
        process.kill()
        raise AttributeError("stdout/stderr is None")

    await asyncio.gather(
        live_stream(process.stdout, sys.stdout),
        live_stream(process.stderr, sys.stderr),
    )


async def git_commit(target_path: Path, message: str):
    process = await asyncio.create_subprocess_exec(
        GIT_PATH,
        "commit",
        "-m",
        message,
        cwd=target_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    if not process.stdout or not process.stderr:
        process.kill()
        raise AttributeError("stdout/stderr is None")

    await asyncio.gather(
        live_stream(process.stdout, sys.stdout),
        live_stream(process.stderr, sys.stderr),
    )


async def git_push(target_path: Path):
    process = await asyncio.create_subprocess_exec(
        GIT_PATH, "push", cwd=target_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    if not process.stdout or not process.stderr:
        process.kill()
        raise AttributeError("stdout/stderr is None")

    await asyncio.gather(
        live_stream(process.stdout, sys.stdout),
        live_stream(process.stderr, sys.stderr),
    )
