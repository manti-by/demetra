import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from redis.exceptions import RedisError
from rq.exceptions import DuplicateJobError

from demetra.library import FIX_REVIEW_FINDINGS_COMMAND_PATTERN, MERGE_COMMAND_PATTERN, REBASE_COMMAND_PATTERN
from demetra.library.constants import CODERABBIT_AUTHOR_LOGINS
from demetra.services.persistence.database import (
    get_session_by_pr_link,
    increment_listener_attempts,
    reset_listener_attempts,
)
from demetra.services.persistence.queue import load_pending_comments, queue, save_pending_comments
from demetra.services.runtime.subprocess import run_command, run_command_to_file
from demetra.services.vcs.github import get_coderabbit_comments
from demetra.settings import BASE_PATH, GITHUB, MAX_ATTEMPTS
from demetra.workflows.comments import run_comments_workflow
from demetra.workflows.merge import run_merge_workflow
from demetra.workflows.rebase import run_rebase_workflow
from demetra.workflows.review_fixes import run_review_fixes_workflow


logger = logging.getLogger(__name__)


async def get_notifications() -> list[dict]:
    """Fetch the current GitHub notifications for the authenticated user.

    Returns:
        list[dict]: The parsed notifications, or an empty list on failure.
    """
    command = [
        str(GITHUB["path"]),
        "api",
        "-H",
        "Accept: application/vnd.github+json",
        "/notifications",
        "--jq",
        ".",
    ]
    # stdout is a single compact JSON line that exceeds the 64KB asyncio pipe
    # readline limit whenever the unread backlog is large; read from a file instead.
    exit_code, stdout, stderr = await run_command_to_file(command=command, target_path=BASE_PATH, disable_stdio=True)
    if exit_code != 0:
        logger.error(f"Failed to fetch notifications: {stderr.strip()}")
        return []
    try:
        return json.loads(stdout) if stdout.strip() else []
    except json.JSONDecodeError:
        logger.error("Failed to parse notifications response")
        return []


def should_process_notification(notification: dict) -> bool:
    """Decide whether a notification is worth processing.

    Only notifications triggered by a mention or a subscription are handled.

    Args:
        notification: The GitHub notification payload.

    Returns:
        bool: True when the notification should be processed.
    """
    return notification.get("reason") in ("mention", "subscribed")


def extract_pr_info(notification: dict) -> dict | None:
    """Extract pull request info from a notification.

    Args:
        notification: The GitHub notification payload.

    Returns:
        dict | None: The PR number, full repository name and title, or None
            when the notification is not about a pull request.
    """
    subject = notification.get("subject", {})
    if subject.get("type") != "PullRequest":
        return None

    url = subject.get("url", "")
    if not url:
        return None

    parts = url.strip("/").split("/")
    try:
        pr_number = int(parts[-1])
    except (ValueError, IndexError):
        return None

    repository = notification.get("repository", {})
    full_name = repository.get("full_name", "")

    if not full_name:
        return None

    return {
        "pr_number": pr_number,
        "full_name": full_name,
        "title": subject.get("title", ""),
    }


def _subject_title(subject: dict) -> str:
    """Return the notification subject title as a plain string.

    Args:
        subject: The notification subject payload.

    Returns:
        str: The title, or an empty string when absent.
    """
    title = subject.get("title")
    return title if isinstance(title, str) else ""


async def fetch_subject_comment(subject: dict) -> dict:
    """Fetch the latest comment of a notification subject.

    Falls back to the subject title when no comment URL is available or the
    request fails. The author login identifies CodeRabbit comments; the id is
    recorded for traceability.

    Args:
        subject: The notification subject payload.

    Returns:
        dict: ``body``, ``author`` and ``id`` of the comment.
    """
    latest_comment_url = subject.get("latest_comment_url")
    if not latest_comment_url:
        return {"body": _subject_title(subject), "author": "", "id": ""}

    command = [
        str(GITHUB["path"]),
        "api",
        latest_comment_url,
        "--jq",
        "{body: .body, author: .user.login, id: .id}",
    ]
    exit_code, stdout, stderr = await run_command_to_file(command=command, target_path=BASE_PATH, disable_stdio=True)
    fallback = {"body": _subject_title(subject), "author": "", "id": ""}
    if exit_code != 0:
        logger.error(f"Failed to fetch subject comment: {stderr.strip()}")
        return fallback
    try:
        comment = json.loads(stdout) if stdout.strip() else {}
    except json.JSONDecodeError:
        logger.error("Failed to parse subject comment response")
        return fallback
    if not isinstance(comment, dict):
        return fallback
    author = comment.get("author")
    return {
        "body": (comment.get("body") or "").strip() or fallback["body"],
        "author": author if isinstance(author, str) else "",
        "id": str(comment.get("id") or ""),
    }


async def fetch_subject_body(subject: dict) -> str | None:
    """Fetch the latest comment body for a notification subject.

    Args:
        subject: The notification subject payload.

    Returns:
        str | None: The comment body or the subject title.
    """
    return (await fetch_subject_comment(subject=subject))["body"] or subject.get("title")


def mentions_demetra_ai_and_merge(body: str | None) -> bool:
    """Check whether a comment body contains the merge command.

    Args:
        body: The comment body, or None.

    Returns:
        bool: True when the merge command pattern is found.
    """
    if not body:
        return False
    return bool(MERGE_COMMAND_PATTERN.search(body))


def mentions_demetra_ai_and_rebase(body: str | None) -> bool:
    """Check whether a comment body contains the rebase command.

    Args:
        body: The comment body, or None.

    Returns:
        bool: True when the rebase command pattern is found.
    """
    if not body:
        return False
    return bool(REBASE_COMMAND_PATTERN.search(body))


def mentions_demetra_ai_and_fix_review_findings(body: str | None) -> bool:
    """Check whether a comment body contains the fix review findings command.

    Args:
        body: The comment body, or None.

    Returns:
        bool: True when the fix review findings command pattern is found.
    """
    if not body:
        return False
    return bool(FIX_REVIEW_FINDINGS_COMMAND_PATTERN.search(body))


def is_coderabbit_author(author: str | None) -> bool:
    """Check whether a comment author is CodeRabbit.

    Args:
        author: The GitHub login of the comment author.

    Returns:
        bool: True when the login belongs to CodeRabbit.
    """
    if not author:
        return False
    return author.removeprefix("@").casefold() in CODERABBIT_AUTHOR_LOGINS


def _submit_comments_workflow(batch: dict) -> bool:
    """Submit the workflow for one batch, at most once per submission attempt.

    The job id is derived from the batch and its attempt counter, and RQ's
    unique enqueue performs the check atomically. A job submitted before a
    failed enqueue call is therefore never submitted a second time, while a
    batch whose submission never reached Redis is picked up on a later poll.

    Args:
        batch: The pending batch payload.

    Returns:
        bool: True when this call submitted a new job.
    """
    batch_id = batch.get("batch_id")
    if not batch_id:
        logger.warning(f"Pending comments for {batch.get('task_id', '')} have no batch id")
        return False
    job_id = f"demetra:comments:{batch_id}:{batch.get('attempt', 0)}"
    try:
        queue.enqueue(
            run_comments_workflow,
            job_id=job_id,
            unique=True,
            task_id=batch["task_id"],
            project_id=batch["project_id"],
            pr_number=batch["pr_number"],
            full_name=batch["full_name"],
        )
        return True
    except DuplicateJobError:
        return False
    except (RedisError, OSError) as e:
        logger.warning(f"Failed to enqueue comments workflow {job_id}: {e}")
        return False


async def process_coderabbit_comments_notification(pr_info: dict) -> bool:
    """Collect all CodeRabbit comments on a PR and enqueue one workflow.

    Comments are saved as a single Redis batch before enqueueing. A pending
    batch is checked before the attempt budget is spent, so duplicate
    notifications cannot exhaust the shared listener budget for the session.

    Args:
        pr_info: The PR info dict with ``pr_number`` and ``full_name``.

    Returns:
        bool: True when the notification can be marked read, False when it
            must stay unread for a later retry (no session, pending batch,
            failed fetch or failed enqueue).
    """
    pr_number, full_name = pr_info["pr_number"], pr_info["full_name"]
    pr_link = f"https://github.com/{full_name}/pull/{pr_number}"

    session = await get_session_by_pr_link(pr_link=pr_link)
    if not session:
        logger.info(f"No session found for PR link: {pr_link}")
        return False

    if pending := load_pending_comments(task_id=session.task_id):
        _submit_comments_workflow(batch=pending)
        logger.info(f"CodeRabbit comments already pending for session {session.task_id}, leaving notification unread")
        return False

    attempts = await increment_listener_attempts(session.task_id)
    max_listener_attempts = MAX_ATTEMPTS["listener"]
    if attempts > max_listener_attempts:
        logger.warning(
            f"Max listener attempts ({max_listener_attempts}) reached for session {session.task_id}, "
            f"giving up on CodeRabbit comments for {pr_link}"
        )
        return True

    if not session.project_id:
        logger.warning(f"Session {session.task_id} has no project_id, cannot enqueue comments workflow")
        return False

    try:
        comments = await get_coderabbit_comments(pr_number=pr_number, full_name=full_name, target_path=BASE_PATH)
    except (OSError, RuntimeError) as e:
        logger.error(f"Failed to fetch CodeRabbit comments for PR #{pr_number}: {e}")
        return False

    if not comments:
        await reset_listener_attempts(session.task_id)
        return True

    batch = {
        "batch_id": uuid4().hex,
        "task_id": session.task_id,
        "project_id": session.project_id,
        "pr_number": pr_number,
        "full_name": full_name,
        "comments": comments,
        "created_at": datetime.now(UTC).isoformat(),
        "attempt": 0,
    }
    saved = save_pending_comments(task_id=session.task_id, comments=batch)
    if saved is None:
        return False
    if not saved:
        logger.info(f"CodeRabbit comments already pending for session {session.task_id}, leaving notification unread")
        return False

    logger.info(
        f"Enqueuing comments workflow for {len(comments)} CodeRabbit comments on PR #{pr_number} in {full_name}"
    )
    if not _submit_comments_workflow(batch=batch):
        logger.warning(
            f"Comments workflow for session {session.task_id} was not submitted, leaving notification unread"
        )
        return False
    await reset_listener_attempts(session.task_id)
    return True


async def mark_notification_read(notification: dict) -> None:
    """Mark a GitHub notification thread as read.

    Args:
        notification: The GitHub notification payload.
    """
    thread_id = notification.get("id")
    if not thread_id:
        return

    command = [
        str(GITHUB["path"]),
        "api",
        "--method",
        "PATCH",
        f"/notifications/threads/{thread_id}",
    ]
    exit_code, _, stderr = await run_command(command=command, target_path=BASE_PATH, disable_stdio=True)
    if exit_code != 0:
        logger.warning(f"Failed to mark notification {thread_id} as read: {stderr.strip()}")


async def process_notification(pr_info: dict, action: str) -> bool:
    """Enqueue a merge or rebase workflow for a PR notification.

    Resolves the session for the PR link, enforces the listener attempt limit,
    and enqueues the matching workflow. The listener attempt counter is reset
    after a successful enqueue.

    Args:
        pr_info: The PR info dict with ``pr_number`` and ``full_name``.
        action: The workflow action, ``"merge"`` or ``"rebase"``.

    Returns:
        bool: True when the workflow was enqueued or the attempt limit was
            reached, otherwise False.
    """
    pr_number, full_name = pr_info["pr_number"], pr_info["full_name"]
    pr_link = f"https://github.com/{full_name}/pull/{pr_number}"

    session = await get_session_by_pr_link(pr_link=pr_link)
    if not session:
        logger.info(f"No session found for PR link: {pr_link}")
        return False

    attempts = await increment_listener_attempts(session.task_id)
    max_listener_attempts = MAX_ATTEMPTS["listener"]
    if attempts > max_listener_attempts:
        logger.warning(
            f"Max listener attempts ({max_listener_attempts}) reached for session {session.task_id}, "
            f"giving up on {action} notification for {pr_link}"
        )
        return True

    if not session.project_id:
        logger.warning(f"Session {session.task_id} has no project_id, cannot enqueue {action} workflow")
        return False

    match action:
        case "merge":
            callable_function = run_merge_workflow
        case "rebase":
            callable_function = run_rebase_workflow
        case "fix_review_findings":
            callable_function = run_review_fixes_workflow
        case _:
            logger.info(f"Unknown action: {pr_link}")
            return False

    logger.info(f"Enqueuing {action} workflow for PR #{pr_number} in {full_name}")
    queue.enqueue(
        callable_function,
        task_id=session.task_id,
        project_id=session.project_id,
        pr_number=pr_number,
        full_name=full_name,
    )
    await reset_listener_attempts(session.task_id)
    return True


async def process_merge_notification(pr_info: dict) -> bool:
    """Process a notification as a merge command.

    Args:
        pr_info: The PR info dict for the notification.

    Returns:
        bool: True when the merge workflow was enqueued.
    """
    return await process_notification(pr_info=pr_info, action="merge")


async def process_rebase_notification(pr_info: dict) -> bool:
    """Process a notification as a rebase command.

    Args:
        pr_info: The PR info dict for the notification.

    Returns:
        bool: True when the rebase workflow was enqueued.
    """
    return await process_notification(pr_info=pr_info, action="rebase")


async def process_fix_review_findings_notification(pr_info: dict) -> bool:
    """Process a notification as a fix review findings command.

    Args:
        pr_info: The PR info dict for the notification.

    Returns:
        bool: True when the review fixes workflow was enqueued.
    """
    return await process_notification(pr_info=pr_info, action="fix_review_findings")
