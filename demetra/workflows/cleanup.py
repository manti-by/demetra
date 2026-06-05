from demetra.library.exceptions import DemetraError
from demetra.library.models import Context
from demetra.services.database import update_session_step
from demetra.services.git import git_add_all, git_cleanup, git_commit, git_push
from demetra.services.github import create_pull_request
from demetra.services.linear import linear_cleanup
from demetra.services.tui import print_message


class PullRequestError(DemetraError):
    pass


async def commit_and_push(context: Context) -> None:
    print_message("Committing changes", style="heading")
    await update_session_step(task_id=context.linear_task.id, step="push")

    await git_add_all(target_path=context.worktree_path)
    await git_commit(target_path=context.worktree_path, message=context.linear_task.full_title)

    print_message("Pushing changes", style="heading")
    await git_push(target_path=context.worktree_path, branch_name=context.branch_name)

    print_message("Creating GitHub PR", style="heading")
    exit_code, stdout, stderr = await create_pull_request(
        target_path=context.worktree_path, branch_name=context.branch_name, title=context.linear_task.full_title
    )
    if exit_code != 0:
        raise PullRequestError(f"Failed to create PR: {stderr or stdout}")
    print_message(stdout.strip(), style="result")

    await update_session_step(task_id=context.linear_task.id, step="completed")


async def cleanup_workflow(context: Context, is_success: bool, should_update_linear_status: bool) -> None:
    if not is_success:
        await update_session_step(task_id=context.linear_task.id, step="failed")

    await git_cleanup(context=context, is_success=is_success)
    if should_update_linear_status:
        await linear_cleanup(context=context, is_success=is_success)
