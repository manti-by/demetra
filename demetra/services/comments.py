import logging
from pathlib import Path

from demetra.library.models import SessionEnvironment
from demetra.services.persistence.queue import clear_pending_comments
from demetra.services.vcs.github import resolve_review_threads


logger = logging.getLogger(__name__)


async def resolve_pending_comments(
    comments: dict,
    target_path: Path,
    environment: SessionEnvironment | None = None,
    project_id: str | None = None,
) -> list[str]:
    """Resolve the saved CodeRabbit threads after their fixes were pushed.

    Acts on the batch handed over by the workflow instead of reloading the key
    by task id, so an older run cannot resolve or clear a newer batch. The
    caller decides whether to retry or release the batch on failure; it is
    removed on success after GitHub confirmed every thread.

    Args:
        comments: The batch payload loaded by the workflow.
        target_path: Directory to run the GitHub CLI in.
        environment: The resolved session environment forwarded to the CLI.
        project_id: Optional project id used for OS env opt-in tokens.

    Returns:
        list[str]: Thread ids still unresolved, empty when every saved thread
            was resolved or there was nothing to resolve.
    """
    task_id = comments.get("task_id", "")
    thread_ids = list(
        dict.fromkeys(
            comment.get("thread_id")
            for comment in comments.get("comments", [])
            if isinstance(comment, dict) and isinstance(comment.get("thread_id"), str) and comment["thread_id"]
        )
    )
    if not thread_ids:
        clear_pending_comments(task_id=task_id, comments=comments)
        return []

    try:
        resolved = await resolve_review_threads(
            thread_ids=thread_ids,
            target_path=target_path,
            environment=environment,
            project_id=project_id,
        )
    except (OSError, RuntimeError) as e:
        logger.error(f"Failed to resolve saved comments for {task_id}: {e}")
        return thread_ids

    if resolved != len(thread_ids):
        logger.warning(f"Resolved {resolved} of {len(thread_ids)} saved threads for {task_id}")
        return thread_ids

    clear_pending_comments(task_id=task_id, comments=comments)
    return []
