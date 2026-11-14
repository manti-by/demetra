import asyncio
import logging.config

from demetra.services.daemons.deployer import run_deploy_cycle
from demetra.settings import DEPLOY, LOGGING


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Deploy origin/master once the commit's CI passed and the jobs drained.

    Runs an infinite loop that reads the remote master commit, gates the
    deploy on the GitHub check runs, waits for the default job queue to drain
    and then runs the deploy steps against the host checkout.
    """
    logger.info(f"Deploy daemon started, polling every {DEPLOY['poll_interval']} seconds")

    while True:
        try:
            await run_deploy_cycle()

        except OSError as e:
            logger.error(f"Error running the deploy cycle: {e}")

        except asyncio.CancelledError:
            logger.info("Poll loop cancelled, shutting down")
            raise

        except Exception:
            logger.exception("Error running the deploy cycle")

        await asyncio.sleep(DEPLOY["poll_interval"])


if __name__ == "__main__":
    asyncio.run(main())
