import asyncio
import logging

from demetra.services.database import init_db
from demetra.services.linear import get_todo_issues
from demetra.services.watcher import process_tasks


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

POLL_INTERVAL = 300


async def main() -> None:
    await init_db()
    logger.info("Process manager started, polling every 5 minutes")

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

        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
