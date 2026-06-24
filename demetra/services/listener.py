import json
import logging

from demetra.library import MERGE_COMMAND_PATTERN, REBASE_COMMAND_PATTERN
from demetra.services.database import get_session_by_pr_link
from demetra.services.queue import queue
from demetra.services.subprocess import run_command
from demetra.settings import BASE_PATH, GITHUB
from demetra.workflows.merge import run_merge_workflow
from demetra.workflows.rebase import run_rebase_workflow


logger = logging.getLogger(__name__)


async def get_notifications() -> list[dict]:
    command = [
        str(GITHUB["path"]),
        "api",
        "-H",
        "Accept: application/vnd.github+json",
        "/notifications",
        "--jq",
        ".",
    ]
    exit_code, stdout, stderr = await run_command(command=command, target_path=BASE_PATH)
    if exit_code != 0:
        logger.error(f"Failed to fetch notifications: {stderr.strip()}")
        return []
    try:
        return json.loads(stdout) if stdout.strip() else []
    except json.JSONDecodeError:
        logger.error("Failed to parse notifications response")
        return []


def should_process_notification(notification: dict) -> bool:
    return notification.get("reason") in ("mention", "subscribed")


def extract_pr_info(notification: dict) -> dict | None:
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
    exit_code, stdout, stderr = await run_command(command=command, target_path=BASE_PATH)
    if exit_code != 0:
        logger.error(f"Failed to fetch subject body: {stderr.strip()}")
        return subject.get("title")
    return stdout.strip() or subject.get("title")


def mentions_demetra_ai_and_merge(body: str | None) -> bool:
    if not body:
        return False
    return bool(MERGE_COMMAND_PATTERN.search(body))


def mentions_demetra_ai_and_rebase(body: str | None) -> bool:
    if not body:
        return False
    return bool(REBASE_COMMAND_PATTERN.search(body))


async def mark_notification_read(notification: dict) -> None:
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
    exit_code, _, stderr = await run_command(command=command, target_path=BASE_PATH)
    if exit_code != 0:
        logger.warning(f"Failed to mark notification {thread_id} as read: {stderr.strip()}")


async def process_merge_notification(pr_info: dict) -> bool:
    pr_number = pr_info["pr_number"]
    full_name = pr_info["full_name"]
    pr_link = f"https://github.com/{full_name}/pull/{pr_number}"

    session = await get_session_by_pr_link(pr_link=pr_link)
    if not session:
        logger.info(f"No session found for PR link: {pr_link}")
        return False

    if not session.project_id:
        logger.warning(f"Session {session.task_id} has no project_id, cannot enqueue merge workflow")
        return False

    logger.info(f"Enqueuing merge workflow for PR #{pr_number} in {full_name}")

    queue.enqueue(
        run_merge_workflow,
        task_id=session.task_id,
        project_id=session.project_id,
        pr_number=pr_number,
        full_name=full_name,
    )

    return True


async def process_rebase_notification(pr_info: dict) -> bool:
    pr_number = pr_info["pr_number"]
    full_name = pr_info["full_name"]
    pr_link = f"https://github.com/{full_name}/pull/{pr_number}"

    session = await get_session_by_pr_link(pr_link=pr_link)
    if not session:
        logger.info(f"No session found for PR link: {pr_link}")
        return False

    if not session.project_id:
        logger.warning(f"Session {session.task_id} has no project_id, cannot enqueue rebase workflow")
        return False

    logger.info(f"Enqueuing rebase workflow for PR #{pr_number} in {full_name}")

    queue.enqueue(
        run_rebase_workflow,
        task_id=session.task_id,
        project_id=session.project_id,
        pr_number=pr_number,
        full_name=full_name,
    )

    return True
