"""Run one worker generation swap for the manual ``make deploy`` path."""

import argparse
import asyncio
import logging.config
import sys
from pathlib import Path

from demetra.library.exceptions import DeployStateError
from demetra.services.daemons.deploy_support import default_state_path, load_state, save_state
from demetra.services.daemons.worker_swap import bootstrap_workers, swap_workers
from demetra.settings import LOGGING


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


def parse_arguments(arguments: list[str]) -> tuple[Path, bool]:
    """Parse the host checkout path and the mode of a worker one-shot.

    Args:
        arguments: The arguments that follow the module name.

    Returns:
        tuple[Path, bool]: The checkout path and whether to bootstrap the slot.
    """
    parser = argparse.ArgumentParser(description="Swap or bootstrap the live worker generation")
    parser.add_argument("--checkout", type=Path, required=True, help="host checkout holding the compose file")
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="scale the recorded live slot instead of swapping generations",
    )
    parsed = parser.parse_args(arguments)
    return parsed.checkout, parsed.bootstrap


async def main() -> int:
    """Swap or bootstrap the worker generations using the shared deploy state.

    Returns:
        int: Zero when staging started and the live generation was signalled,
            or when the recorded live slot was scaled up.
    """
    checkout_path, bootstrap = parse_arguments(arguments=sys.argv[1:])
    state_path = default_state_path()
    state = load_state(path=state_path)
    if bootstrap:
        succeeded = await bootstrap_workers(checkout_path=checkout_path, state_path=state_path, state=state)
    else:
        succeeded = await swap_workers(checkout_path=checkout_path, state_path=state_path, state=state)
    if not succeeded:
        logger.error(f"Worker generation {'bootstrap' if bootstrap else 'swap'} failed")
        try:
            save_state(path=state_path, state=state)
        except DeployStateError:
            logger.error("Failed to checkpoint the worker state after the failure")
        return 1
    logger.info(f"Worker generation {'bootstrap' if bootstrap else 'swap'} succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
