from pathlib import Path

from demetra.services.subprocess import run_command
from demetra.services.tui import print_message
from demetra.settings import GIT_PATH, GIT_WORKTREE_PATH


async def git_worktree_create(target_path: Path, branch_name: str) -> Path:
    worktree_path = GIT_WORKTREE_PATH / branch_name
    command = [str(GIT_PATH), "worktree", "add", "-b", branch_name, str(worktree_path)]
    await run_command(command=command, target_path=target_path)
    return worktree_path


async def git_worktree_remove(target_path: Path, worktree_path: Path, is_error: bool = False):
    command = [str(GIT_PATH), "worktree", "remove", str(worktree_path)]
    if is_error:
        command.append("--force")
    await run_command(command=command, target_path=target_path)


async def git_add_all(target_path: Path):
    command = [str(GIT_PATH), "add", "."]
    await run_command(command=command, target_path=target_path)


async def git_commit(target_path: Path, message: str):
    command = [str(GIT_PATH), "commit", "-m", message]
    await run_command(command=command, target_path=target_path)


async def git_push(target_path: Path):
    command = [str(GIT_PATH), "push"]
    await run_command(command=command, target_path=target_path)


async def git_branch_delete(target_path: Path, branch_name: str):
    command = [str(GIT_PATH), "branch", "-D", branch_name]
    await run_command(command=command, target_path=target_path)


async def git_cleanup(target_path: Path, worktree_path: Path, branch_name: str, *, is_error: bool):
    try:
        print_message("Removing worktree", style="heading")
        await git_worktree_remove(target_path=target_path, worktree_path=worktree_path, is_error=is_error)
    except (OSError, RuntimeError, AttributeError):
        print_message("Failed to remove worktree", style="error")

    if not is_error:
        return
    try:
        print_message("Deleting branch", style="heading")
        await git_branch_delete(target_path=target_path, branch_name=branch_name)
    except (OSError, RuntimeError, AttributeError):
        print_message("Failed to delete branch", style="error")
