import json
import logging

from demetra.library import MERGE_COMMAND_PATTERN, REBASE_COMMAND_PATTERN
from demetra.services.database import (
    get_session_by_pr_link,
    increment_listener_attempts,
    reset_listener_attempts,
)
from demetra.services.queue import queue
from demetra.services.subprocess import run_command
from demetra.settings import BASE_PATH, GITHUB, MAX_LISTENER_ATTEMPTS
from demetra.workflows.merge import run_merge_workflow
from demetra.workflows.rebase import run_rebase_workflow


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
    exit_code, stdout, stderr = await run_command(command=command, target_path=BASE_PATH, disable_stdio=True)
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


async def fetch_subject_body(subject: dict) -> str | None:
    """Fetch the latest comment body for a notification subject.

    Falls back to the subject title when no comment URL is available or the
    request fails.

    Args:
        subject: The notification subject payload.

    Returns:
        str | None: The comment body or the subject title.
    """
    latest_comment_url = subject.get("latest_comment_url")
    if not latest_comment_url:
        return subject.get("title")

    command = [
        str(GITHUB["path"]),
        "api",
        latest_comment_url,
        "--jq",
        ".body",
    ]
    exit_code, stdout, stderr = await run_command(command=command, target_path=BASE_PATH, disable_stdio=True)
    if exit_code != 0:
        logger.error(f"Failed to fetch subject body: {stderr.strip()}")
        return subject.get("title")
    return stdout.strip() or subject.get("title")


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
    if attempts > MAX_LISTENER_ATTEMPTS:
        logger.warning(
            f"Max listener attempts ({MAX_LISTENER_ATTEMPTS}) reached for session {session.task_id}, "
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
