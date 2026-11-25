"""Run one worker generation swap for the manual ``make deploy`` path."""

import argparse
import asyncio
import logging.config
import sys
from pathlib import Path

from demetra.services.daemons.deploy_support import default_state_path, load_state
from demetra.services.daemons.worker_swap import swap_workers
from demetra.settings import LOGGING


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


def parse_arguments(arguments: list[str]) -> Path:
    """Parse the host checkout path of a swap run.

    Args:
        arguments: The arguments that follow the module name.

    Returns:
        Path: The host checkout that holds the compose file and env.
    """
    parser = argparse.ArgumentParser(description="Swap the live worker generation after a deploy")
    parser.add_argument("--checkout", type=Path, required=True, help="host checkout holding the compose file")
    return parser.parse_args(arguments).checkout


async def main() -> int:
    """Swap the worker generations using the shared deploy state.

    Returns:
        int: Zero when staging started and the live generation was signalled.
    """
    checkout_path = parse_arguments(arguments=sys.argv[1:])
    state_path = default_state_path()
    state = load_state(path=state_path)
    if not await swap_workers(checkout_path=checkout_path, state_path=state_path, state=state):
        logger.error("Worker generation swap failed")
        return 1
    logger.info("Worker generation swap succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
