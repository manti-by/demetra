"""Redis deploy lock for the manual ``make deploy`` path.

The deploy daemon takes the lock with redis-py, so a manual deploy has to write
the very same key or the two paths can overlap: a manual ``git pull`` landing
between the daemon's CI gate and its own pull would make the daemon build a
commit whose checks it never read. ``make deploy`` runs on the host, which has
no route to the Redis container, so the key is taken and released through
``docker compose exec redis redis-cli``.
"""

import logging
import uuid
from pathlib import Path
from urllib.parse import urlparse

from demetra.services.daemons.deployer import DEPLOY_LOCK_NAME, deploy_lock_timeout
from demetra.services.runtime.subprocess import run_command
from demetra.settings import DEPLOY, REDIS_URL


logger = logging.getLogger(__name__)

REDIS_SERVICE = "redis"

REDIS_OK = "OK"

RELEASE_SCRIPT = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"


def redis_database(url: str) -> int:
    """Read the database index out of a Redis URL.

    ``redis-cli`` defaults to database 0, while the app uses the database in
    ``REDIS_URL``; without this the manual lock would be written to a key the
    daemon never looks at.

    Args:
        url: The Redis connection URL.

    Returns:
        int: The database index, 0 when the URL names none.
    """
    path = urlparse(url).path.lstrip("/")
    if not path:
        return 0
    try:
        return int(path)
    except ValueError:
        return 0


def redis_cli_command(checkout_path: Path, *arguments: str) -> list[str]:
    """Build a ``redis-cli`` invocation that runs inside the Redis container.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        arguments: The ``redis-cli`` arguments.

    Returns:
        list[str]: The ``docker compose exec`` command.
    """
    compose = [
        str(DEPLOY["docker_path"]),
        "compose",
        "--project-directory",
        str(checkout_path),
        "--env-file",
        str(checkout_path / ".env.docker"),
        "exec",
        "-T",
        REDIS_SERVICE,
        "redis-cli",
        "-n",
        str(redis_database(url=REDIS_URL)),
    ]
    return [*compose, *arguments]


def manual_deploy_timeout(checkout_path: Path) -> int:
    """Return the deadline for the command wrapped by ``make deploy``.

    The manual recipe runs the same steps as the daemon, including the worker
    swap, so it gets the same deadline as the daemon's lease. Bounding the
    wrapped command keeps its release inside the lease even on a partial swap.

    Args:
        checkout_path: The host checkout that holds the compose file and env.

    Returns:
        int: The wrapped command deadline in seconds.
    """
    return deploy_lock_timeout(checkout_path=checkout_path)


async def acquire_manual_deploy_lock(checkout_path: Path) -> str | None:
    """Take the deploy lock the daemon uses, waiting for a running deploy.

    Args:
        checkout_path: The host checkout that holds the compose file and env.

    Returns:
        str | None: The lock token when it was taken, None when a deploy holds it.
    """
    token = uuid.uuid4().hex
    timeout_ms = deploy_lock_timeout(checkout_path=checkout_path) * 1000
    command = redis_cli_command(checkout_path, "SET", DEPLOY_LOCK_NAME, token, "NX", "PX", str(timeout_ms))
    exit_code, stdout, stderr = await run_command(command=command, target_path=checkout_path, disable_stdio=True)
    if exit_code != 0:
        logger.error(f"Failed to reach Redis for the deploy lock: {stderr.strip()}")
        return None
    if stdout.strip() != REDIS_OK:
        return None
    logger.info("Acquired the deploy lock for the manual deploy")
    return token


async def release_manual_deploy_lock(checkout_path: Path, token: str) -> None:
    """Release the deploy lock, but only when it still belongs to this run.

    A plain delete would free the lock of the deploy that took it after this
    run's TTL expired, so the release compares the token first, exactly like
    the daemon's own release.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        token: The token returned by :func:`acquire_manual_deploy_lock`.
    """
    command = redis_cli_command(checkout_path, "EVAL", RELEASE_SCRIPT, "1", DEPLOY_LOCK_NAME, token)
    exit_code, _, stderr = await run_command(command=command, target_path=checkout_path, disable_stdio=True)
    if exit_code != 0:
        logger.error(f"Failed to release the deploy lock: {stderr.strip()}")
        return
    logger.info("Released the deploy lock")
