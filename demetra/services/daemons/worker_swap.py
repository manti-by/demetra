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
# (2N+3), reaping (4), staging start and image read (2), live and legacy lists
# (2), one batch restart disable (1), N signals, the pre-flight slot check (1),
# the deployed-image verification (2) and two checkout reads. Every other
# branch that holds the lease, including reconciliation and maintenance, issues
# fewer commands.
SWAP_STEP_BUDGET = 3 * WORKER_REPLICAS + 17

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


def start_service_command(
    checkout_path: Path, service: str, *, replicas: int, preserve_existing: bool = False
) -> list[str]:
    """Build the command that scales a worker generation without touching others.

    With ``preserve_existing``, Compose leaves already-running containers alone
    even when the mutable image tag now points at a different image. Without
    it, `up` stops and recreates those containers and waits out their stop grace
    period, which can hold workflows for hours.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        service: The Compose service to scale.
        replicas: The target number of containers.
        preserve_existing: Whether to keep containers already in the slot.

    Returns:
        list[str]: The ``docker compose up`` command.
    """
    command = [*compose_command(checkout_path=checkout_path), "up", "--detach", "--no-deps"]
    if preserve_existing:
        command.append("--no-recreate")
    return [*command, "--scale", f"{service}={replicas}", service]


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


async def list_service_image_ids(checkout_path: Path, service: str) -> list[str] | None:
    """List the image ids backing a Compose service's containers.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        service: The Compose service to inspect.

    Returns:
        list[str] | None: The sorted, unique image ids, or None on failure.
    """
    succeeded, output = await run_swap_command(
        checkout_path=checkout_path,
        command=[*compose_command(checkout_path=checkout_path), "images", "--quiet", service],
    )
    return sorted(set(output.split())) if succeeded else None


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


async def pending_swap_containers(checkout_path: Path, service: str, state: DeployState) -> list[str] | None:
    """Return staging containers that belong to a swap awaiting its slot flip.

    A recorded image alone is not enough: the containers must still run that
    image and none of them may be draining, otherwise they are an older
    generation or a live workflow and must not be treated as pending. Replicas
    recorded individually by a failed scale-up stay pending even if the mutable
    tag has since moved to another image, so a retry never force-stops them.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        service: The staging Compose service.
        state: The deploy state recording the image and containers of the
            pending swap.

    Returns:
        list[str] | None: The pending container ids, None when Docker could not
            be queried, and an empty list when there is no pending swap.
    """
    if not state.staging_image_ids:
        return []
    running_ids = await list_container_ids(checkout_path=checkout_path, service=service)
    if running_ids is None:
        return None
    if not running_ids or any(container_id in state.draining_workers for container_id in running_ids):
        return []
    image_ids = await list_service_image_ids(checkout_path=checkout_path, service=service)
    if image_ids is None:
        return None
    if set(image_ids) == set(state.staging_image_ids):
        return running_ids
    recorded_ids = [container_id for container_id in running_ids if container_id in state.staging_worker_ids]
    return recorded_ids if recorded_ids else []


async def _checkpoint_partial_start(checkout_path: Path, state_path: Path, state: DeployState, *, service: str) -> None:
    """Record the replicas a failed scale-up already started, if any.

    ``docker compose up --scale`` can exit nonzero after starting some replicas.
    Their ids and image are checkpointed so the next cycle reconciles them as
    the pending generation instead of treating them as an older, never-signalled
    one and force-stopping the workflows they hold. No marker is recorded when
    no replica started, leaving the slot free for a fresh generation.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        state_path: The JSON deploy state file path.
        state: The deploy state to record the started replicas on.
        service: The staging Compose service.
    """
    running_ids = await list_container_ids(checkout_path=checkout_path, service=service)
    if running_ids is None or not running_ids:
        return
    image_ids = await list_service_image_ids(checkout_path=checkout_path, service=service)
    if image_ids is None or not image_ids:
        return
    state.staging_worker_ids = running_ids
    state.staging_image_ids = image_ids
    _persist_checkpoint(path=state_path, state=state)


async def retire_staging_workers(checkout_path: Path, service: str, state: DeployState) -> bool:
    """Free a staging slot that still holds workers from an earlier generation.

    Containers already recorded in ``state.draining_workers`` are left alone:
    they are draining the workflow they held before the swap, and a second TERM
    would trigger RQ's cold shutdown and lose that work. The slot stays occupied
    until they exit or the watchdog escalates them, so the swap is deferred.
    Containers still running the image recorded by the last swap attempt are
    also kept: that attempt started them but failed before flipping the slot,
    so their workflows must not be force stopped. :func:`reconcile_pending_swap`
    finishes that flip instead. Only containers on an older image are force
    stopped and removed so Compose creates the new image instead of reusing
    them; their jobs are requeued later by :func:`maintain_workers`.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        service: The staging Compose service.
        state: The deploy state whose drain bookkeeping is updated.

    Returns:
        bool: True when the slot is empty and ready for a new generation.
    """
    pending_ids = await pending_swap_containers(checkout_path=checkout_path, service=service, state=state)
    if pending_ids is None:
        return False
    if pending_ids:
        logger.info(f"Keeping current-image workers {pending_ids} in {service} for the pending swap")
        return True
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
    state.staging_image_ids = []
    return True


async def staging_slot_is_available(checkout_path: Path, state: DeployState) -> bool:
    """Check read-only whether the staging slot can take a new generation.

    A slot still holding draining workers is busy: another TERM would start
    RQ's cold shutdown and lose the workflow. Containers that are not draining
    are either empty of work or belong to a swap that failed before its slot
    flip, which :func:`reconcile_pending_swap` finishes on a later cycle.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        state: The deploy state whose drain bookkeeping is consulted.

    Returns:
        bool: True when the slot is empty or holds no draining worker.
    """
    staging_service = worker_service(slot=other_slot(slot=state.worker_slot))
    running_ids = await list_container_ids(checkout_path=checkout_path, service=staging_service)
    if running_ids is None:
        return False
    if any(container_id in state.draining_workers for container_id in running_ids):
        logger.info(f"Staging slot {staging_service} still holds draining workers, deferring the deploy")
        return False
    return True


async def _signal_live_workers(
    checkout_path: Path, state_path: Path, state: DeployState, *, live_service: str
) -> int | None:
    """Signal the live generation once, marking each container as it is sent TERM.

    Legacy ``worker`` containers are listed and signalled alongside the live
    generation even when it is populated: an upgraded stack can keep both, and
    Compose does not remove orphaned containers unless asked to.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        state_path: The JSON deploy state file path.
        state: The deploy state whose drain bookkeeping is updated.
        live_service: The live generation's Compose service.

    Returns:
        int | None: The number of containers signalled, or None on failure.
    """
    live_ids = await list_container_ids(checkout_path=checkout_path, service=live_service)
    if live_ids is None:
        return None
    legacy_ids = await list_container_ids(checkout_path=checkout_path, service=LEGACY_WORKER_SERVICE)
    if legacy_ids is None:
        return None
    container_ids = [
        container_id for container_id in (*live_ids, *legacy_ids) if container_id not in state.draining_workers
    ]
    if not container_ids:
        return 0
    succeeded, _ = await run_swap_command(
        checkout_path=checkout_path, command=disable_restart_command(container_ids=container_ids)
    )
    if not succeeded:
        return None
    for container_id in container_ids:
        succeeded, _ = await run_swap_command(
            checkout_path=checkout_path, command=signal_command(container_ids=[container_id])
        )
        if not succeeded:
            return None
        state.draining_workers[container_id] = time.time()
        if not _persist_checkpoint(path=state_path, state=state):
            return None
    return len(container_ids)


async def reconcile_pending_swap(checkout_path: Path, state_path: Path, state: DeployState) -> bool | None:
    """Finish a swap whose staging generation started before an earlier failure.

    Those containers are never restarted or recreated: the mutable image tag
    may now resolve to a newer image, and `up` would stop them for the whole
    stop grace period while they drain a workflow. Their slot is simply flipped
    to live, so the generation that actually runs is the one whose image was
    recorded by that attempt. A generation left partial by a failed scale-up
    may be promoted as-is: every replica it did start carries the recorded
    image, and stopping them to reach ``WORKER_REPLICAS`` would lose their
    workflows. The caller must not record a later commit as deployed on the
    strength of this reconciliation alone.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        state_path: The JSON deploy state file path.
        state: The deploy state whose live slot is flipped when a swap is pending.

    Returns:
        bool | None: True when a pending swap was reconciled, False when one
            was pending but could not be reconciled, and None when none was
            pending. A failed checkpoint leaves the recorded state, including
            any drain markers, on ``state`` for the caller's later save.
    """
    staging_slot = other_slot(slot=state.worker_slot)
    pending_ids = await pending_swap_containers(
        checkout_path=checkout_path, service=worker_service(slot=staging_slot), state=state
    )
    if pending_ids is None:
        return False
    if not pending_ids:
        return None
    signalled = await _signal_live_workers(
        checkout_path=checkout_path,
        state_path=state_path,
        state=state,
        live_service=worker_service(slot=state.worker_slot),
    )
    if signalled is None:
        return False
    state.worker_slot = staging_slot
    state.staging_image_ids = []
    state.staging_worker_ids = []
    if not _persist_checkpoint(path=state_path, state=state):
        return False
    logger.info(f"Worker generation {staging_slot} is live; {signalled} container(s) are draining")
    return True


async def swap_workers(checkout_path: Path, state_path: Path, state: DeployState) -> bool:
    """Start the staging generation and signal the live one exactly once.

    A pending swap is reconciled first, before any new generation is started:
    its containers are kept and the slot is flipped to them instead of asking
    Compose to recreate them on a newer image, even when only some replicas
    started. A failed reconciliation is not retried in the same call: the slot
    was already mutated by it and starting a generation here would signal the
    wrong side. A staging slot holding an older generation is otherwise
    force-stopped and emptied, so Compose really creates containers from the
    new image; containers from this swap attempt's own start are preserved
    through the start step with ``--no-recreate``, and a failed scale-up
    records the replicas that did start before returning. Exited containers
    are reaped next. Only containers that are not already
    recorded as draining have their restart policy disabled and are signalled,
    so they stay retired after the workflow finishes and a container already
    draining never receives RQ's second, cold-shutdown signal. Each id is
    persisted as soon as its TERM succeeds, so a partial batch failure cannot
    re-signal a container that already switched RQ to the cold-shutdown handler.
    A failed checkpoint aborts the swap rather than reporting success with an
    obsolete state, and the marker it recorded stays on the state for the deploy
    cycle's final save, so a retry reconciles the containers already signalled.
    Legacy ``worker`` containers are discovered and signalled on every swap, so
    orphans left by an upgrade cannot keep taking jobs on the old image.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        state_path: The JSON deploy state file path.
        state: The deploy state, updated with the new roles and drain times.

    Returns:
        bool: True when a pending swap was reconciled or staging started and
            the live generation was signalled.
    """
    outcome = await reconcile_pending_swap(checkout_path=checkout_path, state_path=state_path, state=state)
    if outcome is not None:
        return outcome
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
        command=start_service_command(
            checkout_path=checkout_path, service=staging_service, replicas=WORKER_REPLICAS, preserve_existing=True
        ),
    )
    if not succeeded:
        await _checkpoint_partial_start(
            checkout_path=checkout_path, state_path=state_path, state=state, service=staging_service
        )
        return False
    image_ids = await list_service_image_ids(checkout_path=checkout_path, service=staging_service)
    if image_ids is None or not image_ids:
        return False
    state.staging_worker_ids = []
    state.staging_image_ids = image_ids

    signalled = await _signal_live_workers(
        checkout_path=checkout_path, state_path=state_path, state=state, live_service=live_service
    )
    if signalled is None:
        return False

    state.worker_slot = staging_slot
    state.staging_image_ids = []
    state.staging_worker_ids = []
    if not _persist_checkpoint(path=state_path, state=state):
        return False
    logger.info(f"Worker generation {staging_slot} is live; {signalled} container(s) are draining")
    return True


async def bootstrap_workers(checkout_path: Path, state_path: Path, state: DeployState) -> bool:
    """Scale both generations to match the live slot already in the state.

    A fresh stack has no state file and uses the default blue slot; an existing
    state keeps whichever generation a previous swap made live. The caller holds
    the deploy lock, just as it does for a swap, so `docker-up` cannot change a
    slot while a swap is in flight. A non-live slot that still runs containers
    is left alone: scaling it down would send a second TERM to a worker already
    draining. The checkpoint records the slot even on a fresh stack, so later
    swaps start from the same generation.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        state_path: The JSON deploy state file path.
        state: The deploy state whose live slot selects the replica counts.

    Returns:
        bool: True when both generations were scaled and the state was saved.
    """
    for slot in WORKER_SLOTS:
        service = worker_service(slot=slot)
        replicas = WORKER_REPLICAS if slot == state.worker_slot else 0
        if replicas == 0:
            running_ids = await list_container_ids(checkout_path=checkout_path, service=service)
            if running_ids is None:
                return False
            if running_ids:
                logger.info(f"Keeping running workers {running_ids} in {service}, not scaling the slot down")
                continue
        succeeded, _ = await run_swap_command(
            checkout_path=checkout_path,
            command=start_service_command(checkout_path=checkout_path, service=service, replicas=replicas),
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
    """Reconcile a pending swap, reap, requeue abandoned jobs and escalate hung workers.

    Reconciliation runs at the start of every cycle, under the same deploy lock
    the build takes, so a swap left half-finished by an earlier deploy is flipped
    before another image can be built for the staging slot. Requeueing runs on
    every cycle rather than immediately after a force stop: RQ refreshes a
    running job's registry expiry from the worker heartbeat, so the entry is not
    expired yet at the moment the worker is killed. The call is idempotent and
    the retry on a later cycle is what recovers that job instead of leaving it
    for RQ's cleanup to mark failed.

    Args:
        checkout_path: The host checkout that holds the compose file and env.
        state_path: The JSON deploy state file path.
    """
    state = load_state(path=state_path)
    outcome = await reconcile_pending_swap(checkout_path=checkout_path, state_path=state_path, state=state)
    if outcome is True:
        logger.info("Finished the pending worker swap before the next deploy")
    elif outcome is False:
        logger.warning("Failed to reconcile the pending worker swap, retrying on the next cycle")
    live_service = worker_service(slot=state.worker_slot)
    for service in (*(worker_service(slot=slot) for slot in WORKER_SLOTS), LEGACY_WORKER_SERVICE):
        if not await reap_service(checkout_path=checkout_path, service=service, state=state, live_service=live_service):
            logger.warning(f"Failed to reap the drained containers of {service}, retrying on the next cycle")
    await escalate_draining_workers(checkout_path=checkout_path, state=state)
    recovered = requeue_abandoned_jobs()
    if recovered:
        logger.warning(f"Recovered abandoned workflow jobs {recovered}")
    save_state(path=state_path, state=state)
