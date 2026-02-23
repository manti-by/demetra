from demetra.models import Context
from demetra.services.git import git_add_all, git_cleanup, git_commit, git_push
from demetra.services.github import create_pull_request
from demetra.services.linear import linear_cleanup
from demetra.services.tui import print_message


async def commit_and_push(context: Context) -> None:
    print_message("Committing changes", style="heading")
    await git_add_all(target_path=context.worktree_path)
    await git_commit(target_path=context.worktree_path, message=context.linear_task.full_title)

    print_message("Pushing changes", style="heading")
    await git_push(target_path=context.worktree_path, branch_name=context.branch_name)

    print_message("Creating GitHub PR", style="heading")
    await create_pull_request(
        target_path=context.worktree_path, branch_name=context.branch_name, title=context.linear_task.full_title
    )


async def cleanup_workflow(context: Context, success: bool) -> None:
    await git_cleanup(
        target_path=context.project_path,
        worktree_path=context.worktree_path,
        branch_name=context.branch_name,
        success=success,
    )
    await linear_cleanup(task=context.linear_task, success=success)
