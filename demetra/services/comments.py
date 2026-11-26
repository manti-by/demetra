import logging
from pathlib import Path

from demetra.library.models import SessionEnvironment
from demetra.services.persistence.queue import clear_pending_comments, load_pending_comments
from demetra.services.vcs.github import resolve_review_threads


logger = logging.getLogger(__name__)


async def resolve_pending_comments(
    task_id: str,
    target_path: Path,
    environment: SessionEnvironment | None = None,
    project_id: str | None = None,
) -> bool:
    """Resolve the saved CodeRabbit threads after their fixes were pushed.

    This service leaves the batch in Redis on failure; the caller decides
    whether to retry or release it. It is removed on success after GitHub
    confirmed every thread.

    Args:
        task_id: The task whose pending batch should be resolved.
        target_path: Directory to run the GitHub CLI in.
        environment: The resolved session environment forwarded to the CLI.
        project_id: Optional project id used for OS env opt-in tokens.

    Returns:
        bool: True when every saved thread was resolved or there was nothing
            left to resolve, False when the batch could not be completed.
    """
    payload = load_pending_comments(task_id=task_id)
    if not payload:
        return False

    comments = payload.get("comments", [])
    thread_ids = list(
        dict.fromkeys(
            comment.get("thread_id")
            for comment in comments
            if isinstance(comment, dict) and isinstance(comment.get("thread_id"), str) and comment["thread_id"]
        )
    )
    if not thread_ids:
        clear_pending_comments(task_id=task_id)
        return True

    try:
        resolved = await resolve_review_threads(
            thread_ids=thread_ids,
            target_path=target_path,
            environment=environment,
            project_id=project_id,
        )
    except (OSError, RuntimeError) as e:
        logger.error(f"Failed to resolve saved comments for {task_id}: {e}")
        return False

    if resolved != len(thread_ids):
        logger.warning(f"Resolved {resolved} of {len(thread_ids)} saved threads for {task_id}")
        return False

    clear_pending_comments(task_id=task_id)
    return True
