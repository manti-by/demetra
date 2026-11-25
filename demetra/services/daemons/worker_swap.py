"""Blue/green worker swap for deploys.

The daemon starts the staging generation on the new image, signals the live
generation once so RQ drains the workflow it holds, and leaves reaping and the
hung-workflow watchdog to later poll cycles. The same entry point is used by
the manual deploy through the ``worker-swap`` Compose one-shot.
"""

import logging
import time
from pathlib import Path

from demetra.library.exceptions import DeployStateError
from demetra.library.models import DeployState
from demetra.library.types import WorkerSlot
from demetra.services.daemons.deploy_support import compose_command, load_state, save_state
from demetra.services.persistence.queue import requeue_abandoned_jobs
from demetra.services.runtime.subprocess import run_command
from demetra.settings import DEPLOY, SUBPROCESS_TIMEOUT


logger = logging.getLogger(__name__)

SLOT_BLUE: WorkerSlot = "blue"
SLOT_GREEN: WorkerSlot = "green"
WORKER_SLOTS = (SLOT_BLUE, SLOT_GREEN)

WORKER_SERVICE_PREFIX = "worker-"
LEGACY_WORKER_SERVICE = "worker"
COMPOSE_PROJECT = "demetra"
WORKER_REPLICAS = 4

KILL_GRACE = 60

# Worst-case timeout-bounded commands under one deploy lease: retirement
# (2N+2), reaping (4), staging start (1), live and legacy lists (2), one batch
# restart disable (1), N signals, and two checkout reads. Every other branch
# that holds the lease, including maintenance, issues fewer commands.
SWAP_STEP_BUDGET = 3 * WORKER_REPLICAS + 12

LOG_TAIL_CHARS = 2000


def other_slot(slot: WorkerSlot) -> WorkerSlot:
    """Return the generation that is not currently live.

    Args:
        slot: The live generation.

    Returns:
        WorkerSlot: The staging generation.
    """
    return SLOT_GREEN if slot == SLOT_BLUE else SLOT_BLUE


def worker_service(slot: WorkerSlot) -> str:
    """Return the Compose service name of a generation.

    Args:
        slot: The generation.

    Returns:
        str: The service name.
    """
    return f"{WORKER_SERVICE_PREFIX}{slot}"


def list_containers_command(checkout_path: Path, service: str, *, exited: bool = False) -> list[str]:
    """Build the command that lists the container ids of a service.

    The legacy ``worker`` service no longer exists in the compose file after
    the two-slot upgrade, so its containers are found by their Compose labels
    instead of by service name.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        service: The Compose service to inspect.
        exited: Whether to list exited instead of running containers.

    Returns:
        list[str]: The container listing command.
    """
    if service == LEGACY_WORKER_SERVICE:
        command = [str(DEPLOY["docker_path"]), "ps", "--quiet"]
        if exited:
            command.append("--all")
        command += [
            "--filter",
            f"label=com.docker.compose.project={COMPOSE_PROJECT}",
            "--filter",
            f"label=com.docker.compose.service={LEGACY_WORKER_SERVICE}",
        ]
        if exited:
            command += ["--filter", "status=exited"]
        return command
    command = compose_command(checkout_path=checkout_path)
    command += ["ps", "--quiet"]
    if exited:
        command += ["--all", "--filter", "status=exited"]
    return [*command, service]


def signal_command(container_ids: list[str]) -> list[str]:
    """Build the command that sends one SIGTERM to each container.

    Args:
        container_ids: The containers to signal.

    Returns:
        list[str]: The ``docker kill`` command.
    """
    return [str(DEPLOY["docker_path"]), "kill", "--signal", "TERM", *container_ids]


def disable_restart_command(container_ids: list[str]) -> list[str]:
    """Build the command that keeps a signalled container from being restarted.

    Args:
        container_ids: The containers to stop restarting.

    Returns:
        list[str]: The ``docker update`` command.
    """
    return [str(DEPLOY["docker_path"]), "update", "--restart", "no", *container_ids]


def remove_command(container_ids: list[str], *, force: bool = False) -> list[str]:
    """Build the command that removes containers.

    Args:
        container_ids: The containers to remove.
        force: Whether to remove containers that are still running.

    Returns:
        list[str]: The ``docker rm`` command.
    """
    command = [str(DEPLOY["docker_path"]), "rm"]
    if force:
        command.append("--force")
    return [*command, *container_ids]


def start_service_command(checkout_path: Path, service: str, *, replicas: int) -> list[str]:
    """Build the command that scales a worker generation without touching others.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        service: The Compose service to scale.
        replicas: The target number of containers.

    Returns:
        list[str]: The ``docker compose up`` command.
    """
    return [
        *compose_command(checkout_path=checkout_path),
        "up",
        "--detach",
        "--no-deps",
        "--scale",
        f"{service}={replicas}",
        service,
    ]


async def run_swap_command(checkout_path: Path, command: list[str]) -> tuple[bool, str]:
    """Run one swap command and report its output.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        command: The command to run.

    Returns:
        tuple[bool, str]: Success and the captured stdout.
    """
    logger.info(f"Worker swap command: {' '.join(command)}")
    try:
        exit_code, stdout, stderr = await run_command(
            command=command, target_path=checkout_path, disable_stdio=True, timeout=DEPLOY["step_timeout"]
        )
    except OSError as e:
        logger.error(f"Worker swap command could not be started: {e}")
        return False, ""
    if exit_code != 0:
        output = stderr.strip() or stdout.strip()
        logger.error(f"Worker swap command failed with exit code {exit_code}: {output[-LOG_TAIL_CHARS:]}")
        return False, ""
    return True, stdout.strip()


async def list_container_ids(checkout_path: Path, service: str, *, exited: bool = False) -> list[str] | None:
    """List the container ids of a Compose service.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        service: The Compose service to inspect.
        exited: Whether to list exited instead of running containers.

    Returns:
        list[str] | None: The container ids, or None when the query failed.
    """
    succeeded, output = await run_swap_command(
        checkout_path=checkout_path,
        command=list_containers_command(checkout_path=checkout_path, service=service, exited=exited),
    )
    return output.split() if succeeded else None


def _persist_checkpoint(path: Path, state: DeployState) -> bool:
    """Persist a worker lifecycle checkpoint, reporting a failed state write.

    A failed checkpoint is not swallowed: the caller aborts its operation, so
    the deploy is not recorded as successful with an obsolete state file. The
    drain markers stay on the passed state, which the deploy cycle saves before
    it releases the lease, so a retry reloads what was already signalled before
    it sends another TERM.

    Args:
        path: The JSON deploy state file path.
        state: The state to checkpoint.

    Returns:
        bool: True when the checkpoint was persisted.
    """
    try:
        save_state(path=path, state=state)
    except DeployStateError as e:
        logger.error(f"Worker lifecycle checkpoint failed, aborting: {e}")
        return False
    return True


async def reap_service(
    checkout_path: Path, service: str, state: DeployState, *, live_service: str, scale_down: bool = True
) -> bool:
    """Remove the exited containers of one generation, never signalling them.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        service: The Compose service to reap.
        state: The deploy state whose drain bookkeeping is pruned.
        live_service: The live generation, which must not be scaled to zero.
        scale_down: Whether to scale an empty, non-live slot down to zero.

    Returns:
        bool: True when the reaping commands succeeded.
    """
    exited_ids = await list_container_ids(checkout_path=checkout_path, service=service, exited=True)
    if exited_ids is None:
        return False
    if exited_ids:
        succeeded, _ = await run_swap_command(
            checkout_path=checkout_path, command=remove_command(container_ids=exited_ids)
        )
        if not succeeded:
            return False
        for container_id in exited_ids:
            state.draining_workers.pop(container_id, None)
    if not scale_down or service in (live_service, LEGACY_WORKER_SERVICE):
        return True
    running_ids = await list_container_ids(checkout_path=checkout_path, service=service)
    if running_ids is None:
        return False
    if running_ids:
        return True
    succeeded, _ = await run_swap_command(
        checkout_path=checkout_path,
        command=start_service_command(checkout_path=checkout_path, service=service, replicas=0),
    )
    return succeeded


async def retire_staging_workers(checkout_path: Path, service: str, state: DeployState) -> bool:
    """Free a staging slot that still holds workers from an earlier generation.

    Containers already recorded in ``state.draining_workers`` are left alone:
    they are draining the workflow they held before the swap, and a second TERM
    would trigger RQ's cold shutdown and lose that work. The slot stays occupied
    until they exit or the watchdog escalates them, so the swap is deferred.
    Other running containers come from an older generation that was never
    signalled; they are force stopped and removed so Compose creates the new
    image instead of reusing them, and their jobs are requeued later by
    :func:`maintain_workers`.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        service: The staging Compose service.
        state: The deploy state whose drain bookkeeping is updated.

    Returns:
        bool: True when the slot is empty and ready for a new generation.
    """
    running_ids = await list_container_ids(checkout_path=checkout_path, service=service)
    if running_ids is None:
        return False
    if not running_ids:
        return True
    draining_ids = [container_id for container_id in running_ids if container_id in state.draining_workers]
    if draining_ids:
        logger.info(f"Keeping draining workers {draining_ids} in {service}, deferring the slot reuse")
        return False
    now = time.time()
    for container_id in running_ids:
        succeeded, _ = await run_swap_command(
            checkout_path=checkout_path, command=disable_restart_command(container_ids=[container_id])
        )
        if not succeeded:
            return False
        succeeded, _ = await run_swap_command(
            checkout_path=checkout_path, command=signal_command(container_ids=[container_id])
        )
        if not succeeded:
            return False
        state.draining_workers[container_id] = now
    succeeded, _ = await run_swap_command(
        checkout_path=checkout_path, command=remove_command(container_ids=running_ids, force=True)
    )
    if not succeeded:
        return False
    for container_id in running_ids:
        state.draining_workers.pop(container_id, None)
    return True


async def swap_workers(checkout_path: Path, state_path: Path, state: DeployState) -> bool:
    """Start the staging generation and signal the live one exactly once.

    A staging slot still holding an earlier generation is force-stopped and
    emptied first, so Compose really creates containers from the new image.
    Exited containers are reaped next. Only containers that are not already recorded as
    draining have their restart policy disabled and are signalled, so they stay
    retired after the workflow finishes and a container already draining never
    receives RQ's second, cold-shutdown signal. Each id is persisted as soon
    as its TERM succeeds, so a partial batch failure cannot re-signal a
    container that already switched RQ to the cold-shutdown handler. A failed
    checkpoint aborts the swap rather than reporting success with an obsolete
    state, and the marker it recorded stays on the state for the deploy cycle's
    final save, so a retry reconciles the containers already signalled. On a
    stack that still runs the legacy single ``worker`` service, those are the
    live generation and are signalled once as well.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        state_path: The JSON deploy state file path.
        state: The deploy state, updated with the new roles and drain times.

    Returns:
        bool: True when staging started and the live generation was signalled.
    """
    staging_slot = other_slot(slot=state.worker_slot)
    staging_service = worker_service(slot=staging_slot)
    live_service = worker_service(slot=state.worker_slot)

    if not await retire_staging_workers(checkout_path=checkout_path, service=staging_service, state=state):
        return False
    if not await reap_service(
        checkout_path=checkout_path, service=staging_service, state=state, live_service=live_service, scale_down=False
    ):
        return False
    succeeded, _ = await run_swap_command(
        checkout_path=checkout_path,
        command=start_service_command(checkout_path=checkout_path, service=staging_service, replicas=WORKER_REPLICAS),
    )
    if not succeeded:
        return False

    live_ids = await list_container_ids(checkout_path=checkout_path, service=live_service)
    if live_ids is None:
        return False
    legacy_ids: list[str] = []
    if not live_ids:
        listed_legacy = await list_container_ids(checkout_path=checkout_path, service=LEGACY_WORKER_SERVICE)
        if listed_legacy is None:
            return False
        legacy_ids = listed_legacy
    container_ids = [
        container_id for container_id in (*live_ids, *legacy_ids) if container_id not in state.draining_workers
    ]
    if container_ids:
        succeeded, _ = await run_swap_command(
            checkout_path=checkout_path, command=disable_restart_command(container_ids=container_ids)
        )
        if not succeeded:
            return False
        for container_id in container_ids:
            succeeded, _ = await run_swap_command(
                checkout_path=checkout_path, command=signal_command(container_ids=[container_id])
            )
            if not succeeded:
                return False
            state.draining_workers[container_id] = time.time()
            if not _persist_checkpoint(path=state_path, state=state):
                return False

    state.worker_slot = staging_slot
    if not _persist_checkpoint(path=state_path, state=state):
        return False
    logger.info(f"Worker generation {staging_slot} is live; {len(container_ids)} container(s) are draining")
    return True


async def bootstrap_workers(checkout_path: Path, state_path: Path, state: DeployState) -> bool:
    """Scale both generations to match the live slot already in the state.

    A fresh stack has no state file and uses the default blue slot; an existing
    state keeps whichever generation a previous swap made live. The caller holds
    the deploy lock, just as it does for a swap, so `docker-up` cannot change a
    slot while a swap is in flight. The checkpoint records the slot even on a
    fresh stack, so later swaps start from the same generation.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        state_path: The JSON deploy state file path.
        state: The deploy state whose live slot selects the replica counts.

    Returns:
        bool: True when both generations were scaled and the state was saved.
    """
    for slot in WORKER_SLOTS:
        replicas = WORKER_REPLICAS if slot == state.worker_slot else 0
        succeeded, _ = await run_swap_command(
            checkout_path=checkout_path,
            command=start_service_command(
                checkout_path=checkout_path, service=worker_service(slot=slot), replicas=replicas
            ),
        )
        if not succeeded:
            return False
    return _persist_checkpoint(path=state_path, state=state)


async def escalate_draining_workers(checkout_path: Path, state: DeployState) -> list[str]:
    """Escalate workers whose workflow outlived the job timeout.

    A second SIGTERM is RQ's cold shutdown: it kills the work horse and stops
    the worker, which is the only safe way to reclaim a slot whose workflow
    hung. The job is requeued by :func:`maintain_workers` once its started-job
    registry entry expires, which can happen after the force stop.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        state: The deploy state whose drain times are refreshed.

    Returns:
        list[str]: The container ids that were force-stopped.
    """
    now = time.time()
    escalated: list[str] = []
    for container_id, signalled_at in state.draining_workers.items():
        if now - signalled_at < SUBPROCESS_TIMEOUT + KILL_GRACE:
            continue
        succeeded, running = await run_swap_command(
            checkout_path=checkout_path,
            command=[str(DEPLOY["docker_path"]), "inspect", "--format", "{{.State.Running}}", container_id],
        )
        if not succeeded or running != "true":
            continue
        succeeded, _ = await run_swap_command(
            checkout_path=checkout_path, command=signal_command(container_ids=[container_id])
        )
        if not succeeded:
            continue
        state.draining_workers[container_id] = now
        escalated.append(container_id)
    if escalated:
        logger.warning(f"Force-stopped draining workers {escalated}, awaiting job requeue")
    return escalated


async def maintain_workers(checkout_path: Path, state_path: Path) -> None:
    """Reap drained containers, requeue abandoned jobs and escalate hung workers.

    Requeueing runs on every cycle rather than immediately after a force stop:
    RQ refreshes a running job's registry expiry from the worker heartbeat, so
    the entry is not expired yet at the moment the worker is killed. The call
    is idempotent and the retry on a later cycle is what recovers that job
    instead of leaving it for RQ's cleanup to mark failed.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        state_path: The JSON deploy state file path.
    """
    state = load_state(path=state_path)
    live_service = worker_service(slot=state.worker_slot)
    for service in (*(worker_service(slot=slot) for slot in WORKER_SLOTS), LEGACY_WORKER_SERVICE):
        if not await reap_service(checkout_path=checkout_path, service=service, state=state, live_service=live_service):
            logger.warning(f"Failed to reap the drained containers of {service}, retrying on the next cycle")
    await escalate_draining_workers(checkout_path=checkout_path, state=state)
    requeued = requeue_abandoned_jobs()
    if requeued:
        logger.warning(f"Requeued abandoned workflow jobs {requeued}")
    save_state(path=state_path, state=state)
