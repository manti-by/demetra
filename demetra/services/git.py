from pathlib import Path

from demetra.library.models import Context
from demetra.services.subprocess import run_command
from demetra.services.tui import print_message
from demetra.settings import GIT


async def git_worktree_create(target_path: Path, branch_name: str) -> Path:
    worktree_path = GIT["worktree_path"] / branch_name
    if worktree_path.exists():
        await git_worktree_remove(target_path=target_path, worktree_path=worktree_path, force=True)

    command = [str(GIT["path"]), "worktree", "add", "-b", branch_name, str(worktree_path)]
    await run_command(command=command, target_path=target_path)
    return worktree_path


async def git_worktree_remove(target_path: Path, worktree_path: Path, force: bool = False):
    command = [str(GIT["path"]), "worktree", "remove", str(worktree_path)]
    if force:
        command.append("--force")
    await run_command(command=command, target_path=target_path)


async def git_add_all(target_path: Path):
    command = [str(GIT["path"]), "add", "."]
    await run_command(command=command, target_path=target_path)


async def git_commit(target_path: Path, message: str):
    command = [str(GIT["path"]), "commit", "-m", message]
    await run_command(command=command, target_path=target_path)


async def git_push(target_path: Path, branch_name: str):
    command = [str(GIT["path"]), "push", "--set-upstream", "origin", branch_name]
    await run_command(command=command, target_path=target_path)


async def git_branch_delete(target_path: Path, branch_name: str):
    command = [str(GIT["path"]), "branch", "-D", branch_name]
    await run_command(command=command, target_path=target_path)


async def git_cleanup(context: Context, is_success: bool):
    try:
        print_message("Removing worktree", style="heading")
        await git_worktree_remove(
            target_path=context.project_path, worktree_path=context.worktree_path, force=(not is_success)
        )
    except (OSError, RuntimeError, AttributeError):
        print_message("Failed to remove worktree", style="error")

    if is_success:
        return

    try:
        print_message("Deleting branch", style="heading")
        await git_branch_delete(target_path=context.project_path, branch_name=context.branch_name)
    except (OSError, RuntimeError, AttributeError):
        print_message("Failed to delete branch", style="error")
