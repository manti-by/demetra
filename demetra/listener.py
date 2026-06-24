import asyncio
import logging.config

from demetra.services.database import init_db
from demetra.services.listener import (
    extract_pr_info,
    fetch_subject_body,
    get_notifications,
    mark_notification_read,
    mentions_demetra_ai_and_merge,
    mentions_demetra_ai_and_rebase,
    process_merge_notification,
    process_rebase_notification,
    should_process_notification,
)
from demetra.settings import LISTENER_POLL_INTERVAL, LOGGING


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()
    logger.info(f"GitHub notification listener started, polling every {LISTENER_POLL_INTERVAL} seconds")

    while True:
        try:
            notifications = await get_notifications()

            if not notifications:
                logger.debug("No notifications found")
                await asyncio.sleep(LISTENER_POLL_INTERVAL)
                continue

            for notification in notifications:
                if not should_process_notification(notification=notification):
                    continue

                subject = notification.get("subject", {})
                body = await fetch_subject_body(subject=subject)

                if mentions_demetra_ai_and_merge(body=body):
                    pr_info = extract_pr_info(notification=notification)
                    if not pr_info:
                        continue

                    logger.info(f"Merge requested on {pr_info['full_name']}#{pr_info['pr_number']}: {pr_info['title']}")
                    await process_merge_notification(pr_info=pr_info)
                    await mark_notification_read(notification=notification)

                elif mentions_demetra_ai_and_rebase(body=body):
                    pr_info = extract_pr_info(notification=notification)
                    if not pr_info:
                        continue

                    logger.info(
                        f"Rebase requested on {pr_info['full_name']}#{pr_info['pr_number']}: {pr_info['title']}"
                    )
                    await process_rebase_notification(pr_info=pr_info)
                    await mark_notification_read(notification=notification)

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
