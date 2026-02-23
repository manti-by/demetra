from pathlib import Path

from demetra.services.github import create_pull_request
from demetra.services.git import git_add_all, git_cleanup, git_commit, git_push
from demetra.services.tui import print_message


async def commit_and_push(target_path: Path, branch_name: str, title: str):
    print_message("Committing changes", style="heading")
    await git_add_all(target_path=target_path)
    await git_commit(target_path=target_path, message=title)

    print_message("Pushing changes", style="heading")
    await git_push(target_path=target_path, branch_name=branch_name)


async def create_pr(target_path: Path, branch_name: str, title: str):
    print_message("Creating GitHub PR", style="heading")
    await create_pull_request(target_path=target_path, branch_name=branch_name, title=title)


async def cleanup(project_path: Path, worktree_path: Path, branch_name: str, is_error: bool):
    await git_cleanup(target_path=project_path, worktree_path=worktree_path, branch_name=branch_name, is_error=is_error)
