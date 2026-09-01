import asyncio
import logging.config

from demetra.services.daemons.listener import (
    extract_pr_info,
    fetch_subject_body,
    get_notifications,
    mark_notification_read,
    mentions_demetra_ai_and_fix_review_findings,
    mentions_demetra_ai_and_merge,
    mentions_demetra_ai_and_rebase,
    process_fix_review_findings_notification,
    process_merge_notification,
    process_rebase_notification,
    should_process_notification,
)
from demetra.services.persistence.database import init_db
from demetra.settings import LISTENER_POLL_INTERVAL, LOGGING


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Poll GitHub notifications and process merge/rebase command mentions.

    Runs an infinite loop that fetches notifications, extracts PR info,
    matches merge/rebase commands in the comment bodies, enqueues the
    corresponding workflows and marks processed notifications as read.
    """
    await init_db()
    logger.info(f"GitHub notification listener started, polling every {LISTENER_POLL_INTERVAL} seconds")

    while True:
        try:
            notifications = await get_notifications()

            if not notifications:
                logger.info("No notifications found")
                await asyncio.sleep(LISTENER_POLL_INTERVAL)
                continue

            for notification in notifications:
                if not should_process_notification(notification=notification):
                    continue

                subject = notification.get("subject", {})
                logger.info(f"Processing notification: {subject}")

                if not (body := await fetch_subject_body(subject=subject)):
                    continue
                if not (pr_info := extract_pr_info(notification=notification)):
                    continue

                message = f"requested on {pr_info['full_name']}#{pr_info['pr_number']}: {pr_info['title']}"

                if mentions_demetra_ai_and_merge(body=body):
                    logger.info(f"Merge {message}")
                    processed = await process_merge_notification(pr_info=pr_info)

                elif mentions_demetra_ai_and_rebase(body=body):
                    logger.info(f"Rebase {message}")
                    processed = await process_rebase_notification(pr_info=pr_info)

                elif mentions_demetra_ai_and_fix_review_findings(body=body):
                    logger.info(f"Fix review findings {message}")
                    processed = await process_fix_review_findings_notification(pr_info=pr_info)

                else:
                    continue

                if processed:
                    await mark_notification_read(notification=notification)
                else:
                    logger.warning(f"Notification not marked as read, processing failed: {message}")

        except OSError as e:
            logger.error(f"Error polling GitHub notifications: {e}")

        except asyncio.CancelledError:
            logger.info("Poll loop cancelled, shutting down")
            raise

        except Exception:
            logger.exception("Error polling GitHub notifications")

        await asyncio.sleep(LISTENER_POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
