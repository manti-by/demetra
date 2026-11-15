"""Run a command while holding the shared deploy lock.

``make deploy`` wraps its recipe in this entrypoint so a manual deploy cannot
overlap the deploy daemon. Both paths change the host checkout and rebuild
``mantiby/demetra:latest``, and the daemon takes the same lock, so whichever
path starts second waits for the first one to finish.

Usage: ``python -m demetra.deploy_lock -- <command>``
"""

import asyncio
import sys
from pathlib import Path

from demetra.services.daemons.deploy_lock import (
    acquire_manual_deploy_lock,
    manual_deploy_timeout,
    release_manual_deploy_lock,
)
from demetra.services.runtime.subprocess import run_command
from demetra.services.runtime.tui import print_message


COMMAND_SEPARATOR = "--"


def parse_command(arguments: list[str]) -> list[str]:
    """Strip the ``--`` separator that ``python -m`` keeps in ``sys.argv``.

    Args:
        arguments: The arguments that follow the module name.

    Returns:
        list[str]: The command to run, empty when none was given.
    """
    if arguments[:1] == [COMMAND_SEPARATOR]:
        return arguments[1:]
    return list(arguments)


async def main() -> int:
    """Run the wrapped command under the deploy lock.

    The command is bounded by :func:`manual_deploy_timeout`, so it always stops
    before the lease it holds expires and a second deploy cannot start while
    the wrapped recipe still changes the checkout.

    Returns:
        int: The command exit code, 1 when the lock is held and 2 without a command.
    """
    command = parse_command(arguments=sys.argv[1:])
    if not command:
        print_message(message="Usage: python -m demetra.deploy_lock -- <command>", style="error")
        return 2

    checkout_path = Path.cwd()
    token = await acquire_manual_deploy_lock(checkout_path=checkout_path)
    if token is None:
        print_message(
            message="Could not take the deploy lock, aborting (another deploy may be running)",
            style="error",
        )
        return 1

    try:
        exit_code, _, _ = await run_command(
            command=command,
            target_path=checkout_path,
            timeout=manual_deploy_timeout(checkout_path=checkout_path),
        )
    finally:
        await release_manual_deploy_lock(checkout_path=checkout_path, token=token)
    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
