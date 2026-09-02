import logging
from pathlib import Path

from demetra.library.models import Context, Project, Session
from demetra.services.agents.opencode import opencode_review_fixes_agent
from demetra.services.linear import get_linear_task_by_id
from demetra.services.persistence.database import (
    get_project_by_id_system,
    get_project_environments,
    get_session,
    get_user_environments_decrypted,
)
from demetra.services.persistence.queue import queue
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
from demetra.services.vcs.github import get_pr_info, get_unresolved_review_threads, pr_comment
from demetra.services.wiki import run_wiki_revalidation, write_session_wiki_page
from demetra.settings import WIKI


logger = logging.getLogger(__name__)


def _thread_comments(thread: dict) -> list[dict]:
    """Return the comment nodes of a review thread as plain dicts.

    The GitHub CLI returns comments either as a ``{"nodes": [...]}`` mapping
    or as a bare list depending on the query shape.

    Args:
        thread: A review thread as returned by the GitHub GraphQL API.

    Returns:
        list[dict]: The comment nodes, or an empty list when absent.
    """
    comments = thread.get("comments", {})
    if isinstance(comments, dict):
        nodes = comments.get("nodes", [])
        if not isinstance(nodes, list):
            nodes = []
    elif isinstance(comments, list):
        nodes = comments
    else:
        nodes = []
    return [comment for comment in nodes if isinstance(comment, dict)]


def _format_threads_for_prompt(threads: list[dict]) -> str:
    """Format unresolved threads into a task prompt section.

    Args:
        threads: The unresolved review threads.

    Returns:
        str: Formatted thread descriptions.
    """
    lines: list[str] = []
    for idx, thread in enumerate(threads, 1):
        path = thread.get("path", "")
        line = thread.get("line")
        is_outdated = thread.get("isOutdated", False)
        header = f"Thread {idx}"
        if path:
            header += f" — {path}"
            if line:
                header += f":{line}"
        if is_outdated:
            header += " (outdated)"
        lines.append(header)
        for comment in _thread_comments(thread=thread):
            body = (comment.get("body") or "").strip()
            author = ""
            if isinstance(comment.get("author"), dict):
                author = comment["author"].get("login", "")
            prefix = f"  - {author}: " if author else "  - "
            if body:
                lines.append(f"{prefix}{body}")
            diff_hunk = (comment.get("diffHunk") or "").strip()
            if diff_hunk:
                lines.append(f"    diffHunk: {diff_hunk[:500]}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_threads_for_comment(threads: list[dict]) -> str:
    """Format threads for the PR summary comment.

    Args:
        threads: The unresolved review threads.

    Returns:
        str: Short summary lines.
    """
    lines: list[str] = []
    for idx, thread in enumerate(threads, 1):
        path = thread.get("path", "")
        bodies = [
            body.splitlines()[0][:120]
            for comment in _thread_comments(thread=thread)
            if (body := (comment.get("body") or "").strip())
        ]
        summary = "; ".join(bodies) if bodies else "no body"
        if path:
            lines.append(f"- Thread {idx} ({path}): {summary}")
        else:
            lines.append(f"- Thread {idx}: {summary}")
    return "\n".join(lines)


async def _record_review_fixes_wiki(
    task_id: str, project: Project, session: Session, head_branch: str, worktree_path: Path
) -> None:
    """Write the wiki page for a successful review-fixes run and enqueue revalidation.

    Both steps are best-effort: failures are logged and never affect the
    review-fixes result.

    Args:
        task_id: The Linear task identifier.
        project: The project the PR belongs to.
        session: The session record for the task.
        head_branch: The PR head branch the fixes were pushed to.
        worktree_path: The worktree the fixes were made in.
    """
    try:
        linear_task = await get_linear_task_by_id(task_id=task_id)
        if linear_task is not None:
            context = Context(
                project=project,
                auto_mode=True,
                linear_task=linear_task,
                branch_name=head_branch,
                worktree_path=worktree_path,
                session=session,
            )
            await write_session_wiki_page(context=context)
    except Exception:  # noqa: BLE001
        logger.warning(msg="Failed to write wiki page for review fixes session, continuing")
    if WIKI["revalidation_enabled"]:
        try:
            queue.enqueue(f=run_wiki_revalidation)
        except Exception:  # noqa: BLE001
            logger.warning(msg="Failed to enqueue wiki revalidation, review fixes result unaffected")


async def run_review_fixes_workflow(task_id: str, project_id: str, pr_number: int, full_name: str) -> bool:
    """Fix all unresolved review findings on a PR.

    Loads the session and project, creates a worktree for the PR head branch,
    fetches unresolved review threads, runs the fix agent, commits and pushes,
    and posts a summary comment.

    Args:
        task_id: The Linear task identifier.
        project_id: The project id the PR belongs to.
        pr_number: The pull request number.
        full_name: The repository full name, e.g. ``"owner/repo"``.

    Returns:
        bool: True when the fix workflow succeeded.
    """
    session = await get_session(task_id=task_id)
    if not session:
        logger.error(f"Session not found for task_id: {task_id}")
        return False

    await setup_session_logging(task_id=session.task_id)

    logger.info(f"Starting review fixes workflow for PR #{pr_number} in {full_name}")

    project_data = await get_project_by_id_system(project_id=project_id)
    if not project_data:
        logger.error(f"Project not found for project_id: {project_id}")
        return False

    project = Project(**project_data)
    project.local_path = Path(project.local_path)
    project.environment = await get_project_environments(project_id=project.id, user_id=project.user_id)
    if project.user_id:
        project.user_environment = await get_user_environments_decrypted(user_id=project.user_id)
        project.environment = {**project.user_environment, **project.environment}

    worktree_path = None
    fix_succeeded = False
    head_branch = ""
    try:
        await setup_project_venv(project=project)

        pr_info = await get_pr_info(
            pr_number=pr_number,
            full_name=full_name,
            target_path=project.local_path,
            env=project.environment,
            project_id=project.id,
        )
        if not pr_info:
            return False

        head_branch, base_branch = pr_info

        await git_fetch(target_path=project.local_path, env=project.environment, project_id=project.id)

        validate_ref(head_branch, "head branch")
        validate_ref(base_branch, "base branch")

        worktree_path = await git_worktree_create(
            project=project, branch_name=head_branch, env=project.environment, create_branch=False
        )

        threads = await get_unresolved_review_threads(
            pr_number=pr_number,
            full_name=full_name,
            target_path=worktree_path,
            env=project.environment,
            project_id=project.id,
        )

        if not threads:
            logger.info(f"No unresolved review threads for PR #{pr_number}")
            await pr_comment(
                pr_number=pr_number,
                full_name=full_name,
                body="No unresolved review threads found — nothing to fix.",
                target_path=worktree_path,
                env=project.environment,
                project_id=project.id,
            )
            return True

        print_message(f"Found {len(threads)} unresolved review threads", style="info")

        prompt_threads = _format_threads_for_prompt(threads=threads)
        task = (
            f"Fix all unresolved review findings for PR #{pr_number} in {full_name} "
            f"(head branch `{head_branch}`).\n\n"
            f"Unresolved review threads:\n{prompt_threads}\n\n"
            f"Address every thread. Stage your changes when done."
        )

        exit_code, stdout, stderr = await opencode_review_fixes_agent(
            target_path=worktree_path,
            task=task,
            env=project.environment,
            project_id=project.id,
            user_environment=project.user_environment,
        )
        if exit_code != 0:
            logger.error(f"Review fixes agent failed: {(stderr or stdout).strip()[:500]}")
            return False

        has_staged = await git_add_all(target_path=worktree_path, env=project.environment, project_id=project.id)
        has_committed = False
        if not has_staged:
            has_committed = await git_has_unpushed_commits(
                target_path=worktree_path, branch_name=head_branch, env=project.environment, project_id=project.id
            )
            if not has_committed:
                logger.info(f"Review fixes agent made no changes for PR #{pr_number}")
                await pr_comment(
                    pr_number=pr_number,
                    full_name=full_name,
                    body="Review fixes agent found no changes to apply for the unresolved threads.",
                    target_path=worktree_path,
                    env=project.environment,
                    project_id=project.id,
                )
                return True

        if has_staged:
            await git_commit(
                target_path=worktree_path,
                message=f"fix: address review findings for PR #{pr_number}",
                env=project.environment,
                project_id=project.id,
            )

        await git_force_push(
            target_path=worktree_path, branch_name=head_branch, env=project.environment, project_id=project.id
        )

        comment_body = (
            f"Applied fixes for {len(threads)} unresolved review thread(s) on PR #{pr_number}:\n"
            f"{_format_threads_for_comment(threads=threads)}"
        )
        await pr_comment(
            pr_number=pr_number,
            full_name=full_name,
            body=comment_body,
            target_path=worktree_path,
            env=project.environment,
            project_id=project.id,
        )

        fix_succeeded = True
        logger.info(f"Successfully fixed review findings for PR #{pr_number}")
        return True

    except (OSError, RuntimeError) as e:
        logger.error(f"Failed to process review fixes for PR #{pr_number}: {e}")
        return False

    finally:
        if worktree_path:
            if fix_succeeded:
                await _record_review_fixes_wiki(
                    task_id=task_id,
                    project=project,
                    session=session,
                    head_branch=head_branch,
                    worktree_path=worktree_path,
                )
            try:
                await git_worktree_remove(
                    target_path=project.local_path,
                    worktree_path=worktree_path,
                    env=project.environment,
                    force=True,
                    project_id=project.id,
                )
            except (OSError, RuntimeError):
                logger.warning(msg=f"Failed to clean up worktree at {worktree_path}")
