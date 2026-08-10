from sqlalchemy.exc import SQLAlchemyError

from demetra.library.exceptions import PullRequestError
from demetra.library.models import Context
from demetra.services.agents.opencode import get_opencode_session_tokens
from demetra.services.linear import linear_cleanup
from demetra.services.llm.groq import generate_pr_description
from demetra.services.persistence.database import (
    record_session_step_history,
    update_session_pr_link,
    update_session_step,
)
from demetra.services.runtime.tui import print_message
from demetra.services.vcs.git import git_add_all, git_cleanup, git_commit, git_push
from demetra.services.vcs.github import create_pull_request, extract_pr_link
from demetra.settings import OPENCODE


async def commit_and_push(context: Context) -> bool:
    """Commit, push and open a pull request for the current branch.

    Stages changes, commits with the task title, pushes the branch, generates
    a PR description, creates the PR and records the PR link and final session
    history.

    Args:
        context: The workflow context.

    Returns:
        bool: True when the PR was created, False when there were no files to
            commit.

    Raises:
        PullRequestError: When the PR creation fails.
    """
    print_message("Committing changes", style="heading")

    has_files = await git_add_all(
        target_path=context.worktree_path, env=context.project.environment, project_id=context.project.id
    )
    if not has_files:
        print_message("No files to commit, looping back to build agent", style="warning")
        return False

    await update_session_step(task_id=context.linear_task.id, step="push")
    await git_commit(
        target_path=context.worktree_path,
        message=context.linear_task.full_title,
        env=context.project.environment,
        project_id=context.project.id,
    )

    print_message("Pushing changes", style="heading")
    await git_push(
        target_path=context.worktree_path,
        branch_name=context.branch_name,
        env=context.project.environment,
        project_id=context.project.id,
    )

    print_message("Generating PR description", style="heading")
    task_details = f"{context.linear_task.full_title}\n\n{context.linear_task.description}"
    try:
        pr_body = await generate_pr_description(task_details=task_details, build_plan=context.build_plan)
    except Exception:  # noqa: BLE001
        print_message("Failed to generate PR description, continuing with empty body", style="warning")
        pr_body = ""
    if not pr_body:
        pr_body = ""

    print_message("Creating GitHub PR", style="heading")

    exit_code, stdout, stderr = await create_pull_request(
        target_path=context.worktree_path,
        branch_name=context.branch_name,
        title=context.linear_task.full_title,
        body=pr_body,
        env=context.project.environment,
        project_id=context.project.id,
    )
    if exit_code != 0:
        raise PullRequestError(f"Failed to create PR: {stderr or stdout}")

    print_message(stdout.strip(), style="result")

    if pr_link := extract_pr_link(stdout):
        try:
            await update_session_pr_link(task_id=context.linear_task.id, pr_link=pr_link)
        except SQLAlchemyError:
            print_message("Failed to persist PR link, continuing.", style="warning")

    await update_session_step(task_id=context.linear_task.id, step="completed")

    if context.session_id:
        try:
            usage = await get_opencode_session_tokens(
                target_path=context.worktree_path,
                session_id=context.session_id,
                env=context.project.environment,
            )
            await record_session_step_history(
                session_id=context.session_id,
                step="completed",
                usage=usage,
                model=OPENCODE["build_model"],
            )
        except Exception:  # noqa: BLE001
            print_message("Failed to record session step history, continuing.", style="warning")

    return True


async def cleanup_workflow(
    context: Context,
    is_success: bool,
    should_update_linear_status: bool,
    failure_step: str = "failed",
) -> None:
    """Finalize a workflow run: record history, clean up git and update Linear.

    On failure the session step and token history are recorded under
    ``failure_step``. The worktree is always removed and, when requested, the
    Linear ticket is moved according to the outcome.

    Args:
        context: The workflow context.
        is_success: Whether the workflow completed successfully.
        should_update_linear_status: Whether to move the Linear ticket.
        failure_step: Step name to record on failure.
    """
    if not is_success:
        await update_session_step(task_id=context.linear_task.id, step=failure_step)
        if context.session_id:
            try:
                usage = await get_opencode_session_tokens(
                    target_path=context.worktree_path,
                    session_id=context.session_id,
                    env=context.project.environment,
                )
                await record_session_step_history(
                    session_id=context.session_id,
                    step=failure_step,
                    usage=usage,
                    model=OPENCODE["build_model"],
                )
            except Exception:  # noqa: BLE001
                print_message("Failed to record session step history, continuing.", style="warning")

    await git_cleanup(context=context, is_success=is_success)
    if should_update_linear_status:
        await linear_cleanup(context=context, is_success=is_success)
