import asyncio
from pathlib import Path

from demetra.services.tui import print_message
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

    await asyncio.gather(live_stream(process.stdout), live_stream(process.stderr))
    return worktree_path


async def git_worktree_remove(target_path: Path, worktree_path: Path):
    call = [GIT_PATH, "worktree", "remove", worktree_path]
    process = await asyncio.create_subprocess_exec(
        *call, cwd=target_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    if not process.stdout or not process.stderr:
        process.kill()
        raise AttributeError("stdout/stderr is None")

    await asyncio.gather(live_stream(process.stdout), live_stream(process.stderr))


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

    await asyncio.gather(live_stream(process.stdout), live_stream(process.stderr))


async def git_push(target_path: Path):
    process = await asyncio.create_subprocess_exec(
        GIT_PATH, "push", cwd=target_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    if not process.stdout or not process.stderr:
        process.kill()
        raise AttributeError("stdout/stderr is None")

    await asyncio.gather(live_stream(process.stdout), live_stream(process.stderr))


async def git_branch_delete(target_path: Path, branch_name: str):
    process = await asyncio.create_subprocess_exec(
        GIT_PATH,
        "branch",
        "-D",
        branch_name,
        cwd=target_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    if not process.stdout or not process.stderr:
        process.kill()
        raise AttributeError("stdout/stderr is None")

    await asyncio.gather(live_stream(process.stdout), live_stream(process.stderr))


async def git_cleanup(target_path: Path, worktree_path: Path, branch_name: str, *, is_error: bool):
    try:
        print_message("Removing worktree", style="heading")
        await git_worktree_remove(target_path=target_path, worktree_path=worktree_path)
    except BaseException:  # noqa: BLE001
        print_message("Failed to remove worktree", style="error")

    if is_error:
        try:
            print_message("Deleting branch", style="heading")
            await git_branch_delete(target_path=target_path, branch_name=branch_name)
        except BaseException:  # noqa: BLE001
            print_message("Failed to delete branch", style="error")
