from pathlib import Path

from demetra.services.git import git_worktree_create as _git_worktree_create
from demetra.services.tui import print_message


async def create_worktree(target_path: Path, branch_name: str) -> tuple[Path, str]:
    print_message("Creating feature worktree", style="heading")
    print_message("")
    worktree_path = await _git_worktree_create(target_path=target_path, branch_name=branch_name)
    print_message("")
    print_message(f"Created worktree at: {worktree_path}", style="result")
    return worktree_path, branch_name
