from sqlalchemy.exc import SQLAlchemyError

from demetra.library.exceptions import PrDescriptionError, PullRequestError, WikiError
from demetra.library.models import Context
from demetra.services.agents.opencode import get_opencode_session_tokens
from demetra.services.linear import linear_cleanup
from demetra.services.llm.openrouter import generate_pr_description
from demetra.services.persistence.database import (
    record_session_step_history,
    update_session_pr_link,
    update_session_step,
)
from demetra.services.runtime.tui import print_message
from demetra.services.vcs.git import git_add_all, git_cleanup, git_commit, git_push
from demetra.services.vcs.github import create_pull_request, extract_pr_link
from demetra.services.wiki import write_session_wiki_page
from demetra.settings import OPENCODE


async def commit_and_push(context: Context) -> bool:
    """Commit, push and open a pull request for the current branch.

    Stages the build changes, generates the session wiki page into the
    worktree (so it is part of the same commit), stages the wiki files, commits
    with the task title, pushes the branch, generates a PR description, creates
    the PR and records the PR link and final session history.

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

    print_message("Generating wiki page", style="heading")
    await update_session_step(task_id=context.linear_task.id, step="wiki")
    wiki_error: WikiError | None = None
    try:
        await write_session_wiki_page(context=context, wiki_root=context.worktree_path / "wiki")
    except WikiError as e:
        wiki_error = e
    except Exception as e:  # noqa: BLE001
        wiki_error = WikiError(f"Failed to write wiki page: {e}")
        wiki_error.__cause__ = e
    if wiki_error is None:
        if not await git_add_all(
            target_path=context.worktree_path, env=context.project.environment, project_id=context.project.id
        ):
            print_message("No files to commit after wiki page generation, looping back to build agent", style="warning")
            return False
    else:
        print_message(
            f"Wiki page generation failed: {wiki_error}, committing build changes without wiki page",
            style="warning",
        )

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
        pr_body = await generate_pr_description(
            task_details=task_details,
            build_plan=context.build_plan,
            user_id=context.project.user_id,
        )
    except PrDescriptionError as e:
        raise PullRequestError(f"Failed to generate PR description: {e}") from e
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

    if wiki_error is not None:
        print_message(
            f"Wiki page generation failed ({wiki_error}); commit and PR succeeded without wiki page",
            style="warning",
        )

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
