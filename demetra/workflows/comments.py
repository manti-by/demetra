import logging
from collections.abc import Sequence
from pathlib import Path

from demetra.library.exceptions import DemetraError, ReviewError
from demetra.library.models import Context, Project, SessionEnvironment
from demetra.services.chat import resolve_task_by_id
from demetra.services.comments import resolve_pending_comments
from demetra.services.persistence.database import (
    get_project_by_id_system,
    get_project_environments,
    get_session,
    get_user_environments_decrypted,
    record_session_step,
    reset_listener_attempts,
    update_session_step,
)
from demetra.services.persistence.queue import clear_pending_comments, load_pending_comments, update_pending_comments
from demetra.services.runtime.project import setup_project_venv
from demetra.services.runtime.tui import print_message
from demetra.services.runtime.utils import setup_session_logging
from demetra.services.vcs.git import (
    git_add_all,
    git_commit,
    git_fetch,
    git_force_push,
    git_has_unpushed_commits,
    git_worktree_create,
    git_worktree_remove,
    validate_ref,
)
from demetra.services.vcs.github import get_pr_info, pr_comment
from demetra.workflows.build import run_build_step
from demetra.workflows.review import summarize_findings


logger = logging.getLogger(__name__)


def _format_comments_for_summary(comments: Sequence[object]) -> str:
    """Format saved CodeRabbit comments as raw review text for summarization.

    Args:
        comments: The CodeRabbit comment records saved by the listener.

    Returns:
        str: Comment bodies with their file locations and diff hunks.
    """
    lines: list[str] = []
    for index, comment in enumerate(comments, 1):
        if not isinstance(comment, dict):
            continue
        path = comment.get("path", "")
        line = comment.get("line")
        header = f"Comment {index}"
        if path:
            header += f" — {path}"
            if line:
                header += f":{line}"
        lines.append(header)
        if body := (comment.get("body") or "").strip():
            lines.append(f"  {body}")
        if diff_hunk := (comment.get("diff_hunk") or "").strip():
            lines.append(f"  diffHunk: {diff_hunk[:500]}")
    return "\n".join(lines).strip()


async def _release_batch(task_id: str, comments: dict | None) -> None:
    """Release the pending batch and the listener retry budget for a task.

    Args:
        task_id: The task identifier.
        comments: The batch this run loaded, or None when none was loaded.
    """
    if comments:
        clear_pending_comments(task_id=task_id, comments=comments)
    try:
        await reset_listener_attempts(task_id=task_id)
    except (OSError, RuntimeError) as e:
        logger.warning(f"Failed to reset listener attempts for {task_id}: {e}")


async def _record_failure(task_id: str, message: str) -> None:
    """Record a terminal failure step for a comments workflow run.

    Args:
        task_id: The task identifier.
        message: The failure reason recorded in session history.
    """
    await update_session_step(task_id=task_id, step="failed")
    await record_session_step(task_id=task_id, step="failed", message=message)


async def run_comments_workflow(
    task_id: str, project_id: str, pr_number: int, full_name: str, batch_id: str, attempt: int
) -> bool:
    """Apply a saved batch of CodeRabbit comments to an existing pull request.

    Summarizes the batch with the review step's summarizer, runs the build
    pipeline (which records build, validate, review, lint and test steps),
    force-pushes the result to the PR head branch and resolves the saved
    review threads. The Redis batch is released on every exit, except when
    threads stay unresolved and the batch is kept with a new attempt counter
    for a later workflow to retry. A batch that changed after submission is
    left untouched for its own workflow.

    Args:
        task_id: The task identifier.
        project_id: The project id the PR belongs to.
        pr_number: The pull request number.
        full_name: The repository full name, e.g. ``"owner/repo"``.
        batch_id: The id of the batch submitted by the listener.
        attempt: The submission attempt counter of that batch.

    Returns:
        bool: True when the workflow completed, False on failure.
    """
    batch = load_pending_comments(task_id=task_id)
    if not batch:
        logger.info(f"No pending CodeRabbit comments for task {task_id}")
        return False
    if batch.get("batch_id") != batch_id or batch.get("attempt") != attempt:
        logger.warning(
            f"Pending comments for task {task_id} no longer match submitted batch {batch_id}/{attempt}; "
            f"found {batch.get('batch_id')}/{batch.get('attempt')}"
        )
        return False

    project: Project | None = None
    environment: SessionEnvironment | None = None
    worktree_path: Path | None = None
    retain_batch = False
    try:
        session = await get_session(task_id=task_id)
        if not session:
            logger.error(f"Session not found for task_id: {task_id}")
            return False

        await setup_session_logging(task_id=session.task_id)
        logger.info(f"Starting comments workflow for PR #{pr_number} in {full_name}")

        project_data = await get_project_by_id_system(project_id=project_id)
        if not project_data:
            logger.error(f"Project not found for project_id: {project_id}")
            return False

        project = Project(**project_data)
        project.local_path = Path(project.local_path)
        project.environment = await get_project_environments(project_id=project.id, user_id=project.user_id)
        if project.user_id:
            project.user_environment = await get_user_environments_decrypted(user_id=project.user_id)

        await setup_project_venv(project=project)
        environment = SessionEnvironment(
            project_environment=project.environment, user_environment=project.user_environment
        )

        pr_info = await get_pr_info(
            pr_number=pr_number,
            full_name=full_name,
            target_path=project.local_path,
            environment=environment,
            project_id=project.id,
        )
        if not pr_info:
            return False

        head_branch, base_branch = pr_info
        await git_fetch(target_path=project.local_path, environment=environment, project_id=project.id)
        validate_ref(head_branch, "head branch")
        validate_ref(base_branch, "base branch")

        worktree_path = await git_worktree_create(
            project=project, branch_name=head_branch, environment=environment, create_branch=False
        )

        comments = batch.get("comments", [])
        summary = await summarize_findings(
            review_output=_format_comments_for_summary(comments), task_id=task_id, environment=environment
        )
        if summary is None:
            logger.info(f"No actionable CodeRabbit comments for PR #{pr_number}")
            return True

        task = await resolve_task_by_id(task_id=task_id)
        if task is None:
            logger.error(f"Task not found for task_id: {task_id}")
            return False

        context = Context(
            project=project,
            auto_mode=True,
            task=task,
            branch_name=head_branch,
            worktree_path=worktree_path,
            session=session,
        )
        await run_build_step(build_plan=summary, context=context)

        has_staged = await git_add_all(target_path=worktree_path, environment=environment, project_id=project.id)
        if not has_staged and not await git_has_unpushed_commits(
            target_path=worktree_path, branch_name=head_branch, environment=environment, project_id=project.id
        ):
            logger.info(f"Build agent made no changes for PR #{pr_number}")
            await pr_comment(
                pr_number=pr_number,
                full_name=full_name,
                body="No changes were needed for the CodeRabbit comments.",
                target_path=worktree_path,
                environment=environment,
                project_id=project.id,
            )
            return True

        await update_session_step(task_id=task_id, step="wiki")
        await record_session_step(task_id=task_id, step="wiki")
        await update_session_step(task_id=task_id, step="push")
        await record_session_step(task_id=task_id, step="push")

        if has_staged:
            await git_commit(
                target_path=worktree_path,
                message=f"fix: address CodeRabbit comments for PR #{pr_number}",
                environment=environment,
                project_id=project.id,
            )
        await git_force_push(
            target_path=worktree_path, branch_name=head_branch, environment=environment, project_id=project.id
        )

        unresolved = await resolve_pending_comments(
            comments=batch, target_path=worktree_path, environment=environment, project_id=project.id
        )
        if unresolved:
            logger.warning(f"Failed to resolve saved CodeRabbit threads for PR #{pr_number}: {unresolved}")
            await _record_failure(task_id=task_id, message=f"Unresolved CodeRabbit threads: {', '.join(unresolved)}")
            retry_batch = update_pending_comments(
                task_id=task_id, comments=batch, updates={"attempt": batch.get("attempt", 0) + 1}
            )
            retain_batch = True
            if retry_batch is None:
                logger.warning(f"Could not prepare a retry for unresolved CodeRabbit threads on {task_id}")
            return False

        await pr_comment(
            pr_number=pr_number,
            full_name=full_name,
            body=f"Applied fixes for {len(comments)} CodeRabbit comment(s) on PR #{pr_number}.\n{summary}",
            target_path=worktree_path,
            environment=environment,
            project_id=project.id,
        )
        await update_session_step(task_id=task_id, step="completed")
        await record_session_step(task_id=task_id, step="completed")
        print_message(f"Applied CodeRabbit comments for PR #{pr_number}", style="result")
        return True

    except ReviewError as e:
        logger.error(f"Failed to summarize CodeRabbit comments for PR #{pr_number}: {e}")
        await _record_failure(task_id=task_id, message=str(e))
        return False
    except DemetraError as e:
        logger.error(f"Workflow error while processing CodeRabbit comments for PR #{pr_number}: {e}")
        await _record_failure(task_id=task_id, message=str(e))
        return False
    except (OSError, RuntimeError) as e:
        logger.error(f"Failed to process CodeRabbit comments for PR #{pr_number}: {e}")
        await _record_failure(task_id=task_id, message=str(e))
        return False
    finally:
        try:
            if not retain_batch:
                await _release_batch(task_id=task_id, comments=batch)
        finally:
            if worktree_path and project:
                try:
                    await git_worktree_remove(
                        target_path=project.local_path,
                        worktree_path=worktree_path,
                        environment=environment,
                        force=True,
                        project_id=project.id,
                    )
                except (OSError, RuntimeError):
                    logger.warning(msg=f"Failed to clean up worktree at {worktree_path}")
