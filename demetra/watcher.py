import asyncio
import logging.config

from demetra.services.daemons.watcher import process_tasks
from demetra.services.linear import get_todo_issues
from demetra.services.persistence.database import init_db
from demetra.settings import LOGGING, WATCHER_POLL_INTERVAL


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Poll Linear for TODO issues and enqueue their workflows.

    Runs an infinite loop that fetches TODO tasks, upserts pending sessions
    and queues a workflow run for each task.
    """
    await init_db()
    logger.info(f"Process manager started, polling every {WATCHER_POLL_INTERVAL} seconds")

    while True:
        try:
            logger.debug("Polling Linear API for TODO issues")
            tasks = await get_todo_issues()

            if tasks:
                await process_tasks(tasks=tasks)
            else:
                logger.info("No TODO issues found")

        except OSError as e:
            logger.error(f"Error polling Linear: {e}")

        except asyncio.CancelledError:
            logger.info("Poll loop cancelled, shutting down")
            raise

        except Exception:
            logger.exception("Error polling Linear")

        await asyncio.sleep(WATCHER_POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
