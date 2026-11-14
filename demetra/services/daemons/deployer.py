"""Deploy daemon — deploy origin/master once its CI passed and the queue drained.

Follow-up: MNT-316 — merge the watcher, the listener and the deploy daemon into
one universal watcher.
"""

import asyncio
import json
import logging
import os
import shlex
import time
from dataclasses import asdict
from pathlib import Path

from demetra.library.models import DeployState
from demetra.services.persistence.queue import connection, queue
from demetra.services.runtime.subprocess import run_command
from demetra.settings import DEPLOY


logger = logging.getLogger(__name__)

CI_STATUS_PASSED = "passed"
CI_STATUS_PENDING = "pending"
CI_STATUS_FAILED = "failed"
CI_STATUS_UNKNOWN = "unknown"

SUCCESSFUL_CONCLUSIONS = ("success", "neutral", "skipped")

OPTIONAL_STEPS = ("pull_images", "nginx_reload")

PULL_STEP = "pull"

RECREATE_STEP = "up"

SETPRIV_COMMAND = "setpriv"

DEPLOY_IMAGE = "mantiby/demetra:latest"

DEPLOY_SERVICE = "deployer"

DOCKER_SOCKET = "/var/run/docker.sock"

DRAIN_POLL_INTERVAL = 15

DEPLOY_LOCK_NAME = "demetra:deployer"

LOG_TAIL_CHARS = 2000


def parse_remote_sha(stdout: str) -> str | None:
    """Parse the commit sha out of a ``git ls-remote`` line.

    Args:
        stdout: The ``git ls-remote origin refs/heads/master`` output.

    Returns:
        str | None: The remote commit sha, or None when the output is empty.
    """
    line = stdout.strip()
    if not line:
        return None
    return line.split()[0] or None


def parse_repository_slug(url: str) -> str | None:
    """Extract the ``owner/repo`` slug from a git remote URL.

    Handles both ``https://github.com/owner/repo.git`` and
    ``git@github.com:owner/repo.git`` remotes.

    Args:
        url: The ``git remote get-url origin`` output.

    Returns:
        str | None: The repository slug, or None when the URL has no path.
    """
    candidate = url.strip().removesuffix(".git")
    if not candidate:
        return None
    parts = candidate.replace(":", "/").rstrip("/").split("/")
    if len(parts) < 2 or not parts[-1] or not parts[-2]:
        return None
    return f"{parts[-2]}/{parts[-1]}"


def summarize_check_runs(payload: dict) -> str:
    """Reduce a GitHub check-runs payload to a single deploy gate status.

    A commit without check runs counts as pending: the workflow run may not
    exist yet when a fresh push is first polled. Neutral and skipped
    conclusions count as success because they do not report a failing check.

    Args:
        payload: The ``/commits/{sha}/check-runs`` response.

    Returns:
        str: ``"passed"``, ``"pending"`` or ``"failed"``.
    """
    runs = payload.get("check_runs") or []
    if not runs:
        return CI_STATUS_PENDING
    if any(run.get("status") != "completed" for run in runs):
        return CI_STATUS_PENDING
    if any(run.get("conclusion") not in SUCCESSFUL_CONCLUSIONS for run in runs):
        return CI_STATUS_FAILED
    return CI_STATUS_PASSED


def should_deploy(state: DeployState, sha: str, now: float) -> bool:
    """Decide whether a commit is due for a deploy.

    Args:
        state: The persisted deploy state.
        sha: The current origin/master commit.
        now: The current POSIX timestamp.

    Returns:
        bool: True when the commit is not deployed yet and the minimum
            interval between two deploys has elapsed.
    """
    if sha == state.last_deployed_sha:
        return False
    return now - state.last_deploy_at >= DEPLOY["min_interval"]


def is_queue_drained() -> bool:
    """Return whether the default job queue has neither a waiting nor a running job.

    Returns:
        bool: True when the queue is empty and no job is in progress.
    """
    if queue.count > 0:
        return False
    return not queue.started_job_registry.get_job_ids()


def checkout_owner_prefix(checkout_path: Path) -> list[str]:
    """Return the ``setpriv`` prefix that runs a git command as the checkout owner.

    The daemon runs as root, so a plain ``git pull`` would write root-owned
    objects, refs and working-tree files into the host checkout, leaving the
    host user unable to create loose objects or run ``git gc`` there. Dropping
    to the checkout's own uid/gid keeps the ownership intact. Supplementary
    groups are cleared rather than initialized because the host uid may have no
    passwd entry inside the container, where ``--init-groups`` would fail and
    git needs nothing beyond its primary group.

    Args:
        checkout_path: The host checkout the daemon deploys.

    Returns:
        list[str]: The prefix to prepend to a git command, empty when the
            daemon already runs as a non-root user.
    """
    if os.geteuid() != 0:
        return []
    checkout_stat = checkout_path.stat()
    return [
        SETPRIV_COMMAND,
        f"--reuid={checkout_stat.st_uid}",
        f"--regid={checkout_stat.st_gid}",
        "--clear-groups",
    ]


def default_state_path() -> Path:
    """Resolve the deploy state file path.

    The default lives in the deployer's own volume, never in the app home
    volume: the daemon runs as root, so a state directory created there would
    be root-owned and would block the ``demetra`` user's own ``~/.demetra``
    tree (worktrees, venvs) in the shared ``demetra_app_data`` volume.

    Returns:
        Path: The configured path, defaulting to the deployer state volume.
    """
    if state_path := DEPLOY["state_path"]:
        return state_path
    return Path("/var/lib/demetra/deployer-state.json")


def load_state(path: Path) -> DeployState:
    """Load the persisted deploy state.

    A missing file is a fresh daemon; an unreadable file is logged and treated
    as an empty state so a corrupt state never stops the daemon.

    Args:
        path: The JSON state file path.

    Returns:
        DeployState: The persisted state, or an empty state.
    """
    if not path.exists():
        return DeployState()
    try:
        return DeployState.from_payload(json.loads(path.read_text()))
    except (OSError, TypeError, ValueError):
        logger.exception(f"Failed to read the deploy state from {path}")
        return DeployState()


def save_state(path: Path, state: DeployState) -> None:
    """Persist the deploy state, logging instead of failing the cycle.

    Args:
        path: The JSON state file path.
        state: The state to write.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(state), indent=2))
    except OSError:
        logger.exception(f"Failed to write the deploy state to {path}")


def build_deploy_steps(checkout_path: Path) -> list[tuple[str, list[str]]]:
    """Build the ordered deploy commands for the host checkout.

    Mirrors the ``deploy`` target in the Makefile. The ``deployer`` service is
    deliberately absent from the ``up`` list: the daemon must not recreate
    itself while it runs the deploy. The pull runs as the checkout owner so the
    new objects and files keep the host user's ownership. Every command names
    the checkout explicitly (``--project-directory`` for compose, an absolute
    build context) so the daemon never depends on its own working directory,
    which is the image-owned module root rather than the writable checkout.

    Args:
        checkout_path: The host checkout the daemon deploys.

    Returns:
        list[tuple[str, list[str]]]: The step name and command pairs.
    """
    docker = str(DEPLOY["docker_path"])
    git = str(DEPLOY["git_path"])
    checkout = str(checkout_path)
    compose = [docker, "compose", "--project-directory", checkout, "--env-file", str(checkout_path / ".env.docker")]
    owner = checkout_owner_prefix(checkout_path=checkout_path)
    steps = [
        (PULL_STEP, [*owner, git, "-c", f"safe.directory={checkout_path}", "pull", "--ff-only"]),
        ("build", [docker, "build", "--platform", "linux/amd64", "--tag", DEPLOY_IMAGE, checkout]),
        ("pull_images", [*compose, "pull", "postgres", "redis", "react-build"]),
        ("migrate", [*compose, "up", "--abort-on-container-failure", "migrate", "react-build"]),
        (
            "up",
            [*compose, "up", "--detach", "--force-recreate", "--scale", "worker=2", *DEPLOY["compose_services"]],
        ),
    ]
    if reload_command := shlex.split(DEPLOY["nginx_reload_command"]):
        steps.append(("nginx_reload", reload_command))
    return steps


def deploy_lock_timeout(checkout_path: Path) -> int:
    """Return a lock TTL that covers a whole multi-step deploy.

    Every step is bounded by ``step_timeout``, and the recreate step first
    waits for the queue with ``drain_timeout`` while the lock is already held,
    so the TTL is the sum of both. A shorter TTL would let the lock expire
    mid-deploy and allow a second daemon to start a concurrent one.

    Args:
        checkout_path: The host checkout the daemon deploys.

    Returns:
        int: The lock TTL in seconds.
    """
    return len(build_deploy_steps(checkout_path=checkout_path)) * DEPLOY["step_timeout"] + DEPLOY["drain_timeout"]


async def get_remote_master_sha(checkout_path: Path) -> str | None:
    """Read the current origin/master commit without mutating the checkout.

    ``git ls-remote`` is read-only, so polling cannot collide with the git
    operations the app runs in the same repository.

    Args:
        checkout_path: The host checkout the daemon deploys.

    Returns:
        str | None: The remote commit sha, or None when the command fails.
    """
    git = str(DEPLOY["git_path"])
    command = [*checkout_owner_prefix(checkout_path=checkout_path)]
    command += [git, "-c", f"safe.directory={checkout_path}", "ls-remote", "origin", "refs/heads/master"]
    exit_code, stdout, stderr = await run_command(command=command, target_path=checkout_path, disable_stdio=True)
    if exit_code != 0:
        logger.error(f"Failed to read origin/master: {stderr.strip()}")
        return None
    return parse_remote_sha(stdout=stdout)


async def get_checkout_head_sha(checkout_path: Path) -> str | None:
    """Read the commit currently checked out in the host checkout.

    Args:
        checkout_path: The host checkout the daemon deploys.

    Returns:
        str | None: The checked-out commit sha, or None when the command fails.
    """
    git = str(DEPLOY["git_path"])
    command = [*checkout_owner_prefix(checkout_path=checkout_path)]
    command += [git, "-c", f"safe.directory={checkout_path}", "rev-parse", "HEAD"]
    exit_code, stdout, stderr = await run_command(command=command, target_path=checkout_path, disable_stdio=True)
    if exit_code != 0:
        logger.error(f"Failed to read the checked-out commit: {stderr.strip()}")
        return None
    return stdout.strip() or None


async def get_origin_repository(checkout_path: Path) -> str | None:
    """Resolve the ``owner/repo`` slug tracked by the checkout's origin remote.

    Args:
        checkout_path: The host checkout the daemon deploys.

    Returns:
        str | None: The repository slug, or None when it cannot be resolved.
    """
    git = str(DEPLOY["git_path"])
    command = [*checkout_owner_prefix(checkout_path=checkout_path)]
    command += [git, "-c", f"safe.directory={checkout_path}", "remote", "get-url", "origin"]
    exit_code, stdout, stderr = await run_command(command=command, target_path=checkout_path, disable_stdio=True)
    if exit_code != 0:
        logger.error(f"Failed to read the origin remote: {stderr.strip()}")
        return None
    return parse_repository_slug(url=stdout)


async def get_ci_status(sha: str, repository: str) -> str:
    """Read the GitHub check-run status of a commit.

    A read failure is reported as ``unknown`` rather than failed: a transient
    ``gh``/API error must not be mistaken for red check runs, which would
    record a failure for a commit that may well be green.

    Args:
        sha: The commit to inspect.
        repository: The ``owner/repo`` slug owning the commit.

    Returns:
        str: ``"passed"``, ``"pending"``, ``"failed"`` or ``"unknown"`` when
            the status could not be read.
    """
    command = [str(DEPLOY["github_path"]), "api", f"repos/{repository}/commits/{sha}/check-runs"]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=DEPLOY["host_checkout"], disable_stdio=True
    )
    if exit_code != 0:
        logger.warning(f"Failed to read the check runs for {sha}: {stderr.strip()}")
        return CI_STATUS_UNKNOWN
    try:
        payload = json.loads(stdout) if stdout.strip() else {}
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse the check runs for {sha}")
        return CI_STATUS_UNKNOWN
    return summarize_check_runs(payload=payload)


async def wait_for_queue_drain(timeout: int) -> bool:
    """Wait until the default job queue drains or the timeout expires.

    Args:
        timeout: Maximum seconds to wait for the running jobs.

    Returns:
        bool: True when the queue drained, False on timeout.
    """
    deadline = time.monotonic() + timeout
    while not is_queue_drained():
        if time.monotonic() >= deadline:
            logger.warning(f"Job queue still busy after {timeout} seconds, skipping this deploy")
            return False
        await asyncio.sleep(DRAIN_POLL_INTERVAL)
    return True


async def run_deploy_step(name: str, command: list[str], checkout_path: Path) -> bool:
    """Run one deploy command and log its outcome.

    Args:
        name: The step name used in the log lines.
        command: The command to run.
        checkout_path: Working directory of the command.

    Returns:
        bool: True when the command exited with a zero code.
    """
    logger.info(f"Deploy step '{name}' started: {' '.join(command)}")
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=checkout_path, timeout=DEPLOY["step_timeout"]
    )
    if exit_code != 0:
        output = stderr.strip() or stdout.strip()
        logger.error(f"Deploy step '{name}' failed with exit code {exit_code}: {output[-LOG_TAIL_CHARS:]}")
        return False
    logger.info(f"Deploy step '{name}' succeeded")
    return True


async def checkout_matches_sha(checkout_path: Path, sha: str) -> bool:
    """Confirm the checkout still holds the commit whose CI passed.

    ``git pull --ff-only`` fast-forwards to whatever ``origin/master`` points
    to at pull time, so master can advance between the gate check and the pull.
    Building that newer commit would ship code whose CI was never checked, so
    the deploy aborts and the next cycle gates the new commit instead.

    Args:
        checkout_path: The host checkout the daemon deploys.
        sha: The gated commit the deploy is allowed to build.

    Returns:
        bool: True when the checkout is at the gated commit.
    """
    head_sha = await get_checkout_head_sha(checkout_path=checkout_path)
    if head_sha != sha:
        logger.error(f"Checkout is at {head_sha} instead of the gated commit {sha}, aborting the deploy")
        return False
    return True


def recreate_deployer_command(checkout_path: Path) -> list[str]:
    """Build the detached helper command that recreates the deployer container.

    The daemon runs the image-baked copy of its own code, so a new image only
    takes effect once the container is recreated — but the deployer cannot
    ``docker compose up`` its own service, because recreating the container
    kills the process that runs the command. A throwaway helper container
    drives the host daemon instead, and it is started detached so the deployer
    being killed cannot abort the recreate.

    Args:
        checkout_path: The host checkout the daemon deploys.

    Returns:
        list[str]: The ``docker run`` command starting the helper.
    """
    docker = str(DEPLOY["docker_path"])
    checkout = str(checkout_path)
    return [
        docker,
        "run",
        "--detach",
        "--rm",
        "--user",
        "0",
        "--entrypoint",
        "docker",
        "--volume",
        f"{DOCKER_SOCKET}:{DOCKER_SOCKET}",
        "--volume",
        f"{checkout}:{checkout}",
        DEPLOY_IMAGE,
        "compose",
        "--file",
        str(checkout_path / "docker-compose.yaml"),
        "--project-directory",
        checkout,
        "--env-file",
        str(checkout_path / ".env.docker"),
        "up",
        "--detach",
        "--force-recreate",
        DEPLOY_SERVICE,
    ]


async def recreate_deployer(checkout_path: Path) -> bool:
    """Recreate the deployer container so it runs the image just built.

    Without this the daemon keeps executing the code baked when its own
    container was created, so every fix to the daemon would need a manual
    ``make deploy`` and the running container would drift from master. A
    failure is logged and does not invalidate the deploy that already
    succeeded.

    Args:
        checkout_path: The host checkout the daemon deploys.

    Returns:
        bool: True when the helper container was started.
    """
    command = recreate_deployer_command(checkout_path=checkout_path)
    logger.info(f"Recreating the deployer container with the new image: {' '.join(command)}")
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=checkout_path, disable_stdio=True, timeout=DEPLOY["step_timeout"]
    )
    if exit_code != 0:
        output = stderr.strip() or stdout.strip()
        logger.error(f"Failed to recreate the deployer container: {output[-LOG_TAIL_CHARS:]}")
        return False
    logger.info("Deployer container recreate dispatched")
    return True


async def run_deploy(checkout_path: Path, sha: str) -> bool:
    """Run the deploy steps in order, stopping at the first required failure.

    The image pull and the nginx reload are optional: the Makefile tolerates a
    failed pull, and a failed reload leaves the previous nginx configuration
    serving, which does not invalidate the containers that were already
    recreated. Treating the reload as required would retry the whole
    destructive sequence, migrations included, every minimum interval.

    The default queue is drained again immediately before the containers are
    recreated: the gate the cycle ran can be an hour stale by then, because the
    build and the migration sit in between, and a job that started meanwhile
    would be killed by ``--force-recreate``.

    Args:
        checkout_path: The host checkout the daemon deploys.
        sha: The gated commit the deploy is allowed to build.

    Returns:
        bool: True when every required step succeeded.
    """
    for name, command in build_deploy_steps(checkout_path=checkout_path):
        if name == RECREATE_STEP and not await wait_for_queue_drain(timeout=DEPLOY["drain_timeout"]):
            logger.error("Job queue busy again while preparing the deploy, deferring the container recreate")
            return False
        succeeded = await run_deploy_step(name=name, command=command, checkout_path=checkout_path)
        if not succeeded:
            if name in OPTIONAL_STEPS:
                logger.warning(f"Deploy step '{name}' failed, continuing with the deploy")
                continue
            logger.error(f"Deploy aborted at step '{name}'")
            return False
        if name == PULL_STEP and not await checkout_matches_sha(checkout_path=checkout_path, sha=sha):
            return False
    return True


async def run_deploy_cycle() -> None:
    """Run one deploy poll: detect a new commit, gate on CI, drain and deploy.

    The remote commit is re-read after the queue drains so a push that landed
    during the drain is left to the next cycle instead of deploying stale code.
    A single Redis lock, kept for the length of the whole deploy, keeps one
    deploy at a time even if two daemon containers overlap. The deployer is
    recreated from the new image only after a successful deploy, once the state
    is persisted and the lock is released, so the replacement daemon does not
    start deployed-blind or blocked by its own lock.
    """
    checkout_path = DEPLOY["host_checkout"]
    sha = await get_remote_master_sha(checkout_path=checkout_path)
    if not sha:
        return

    state_path = default_state_path()
    state = load_state(path=state_path)
    if not state.last_deployed_sha:
        head_sha = await get_checkout_head_sha(checkout_path=checkout_path)
        if head_sha:
            state.last_deployed_sha = head_sha
            save_state(path=state_path, state=state)
            logger.info(f"Seeded the deploy state from the checked-out commit {head_sha}")

    if not should_deploy(state=state, sha=sha, now=time.time()):
        logger.debug(f"No deploy due for origin/master {sha}")
        return

    repository = DEPLOY["repository"] or await get_origin_repository(checkout_path=checkout_path)
    if not repository:
        logger.error("Unable to resolve the GitHub repository for the CI check")
        return

    ci_status = await get_ci_status(sha=sha, repository=repository)
    if ci_status == CI_STATUS_UNKNOWN:
        # A read failure says nothing about the commit: never record it as a
        # failure, or a single `gh api` blip would misreport (and dedupe) a
        # commit that may well be green on the next poll.
        logger.warning(f"Could not read the check runs for {sha}, retrying on the next poll")
        return
    if ci_status == CI_STATUS_FAILED:
        failure = f"CI checks {ci_status}"
        if state.last_failed_sha != sha or state.last_error != failure:
            logger.error(f"CI checks for {sha} failed, not deploying")
            state.last_failed_sha = sha
            state.last_error = failure
            save_state(path=state_path, state=state)
        return
    if ci_status != CI_STATUS_PASSED:
        logger.info(f"CI checks for {sha} are {ci_status}, not deploying yet")
        return
    if state.last_failed_sha == sha:
        # A re-run turned this commit green: drop the stale failure marker so
        # the deduplication above cannot swallow a later, different failure.
        state.last_failed_sha = None
        state.last_error = None
        save_state(path=state_path, state=state)

    if not await wait_for_queue_drain(timeout=DEPLOY["drain_timeout"]):
        return

    current_sha = await get_remote_master_sha(checkout_path=checkout_path)
    if current_sha != sha:
        logger.info(f"origin/master moved to {current_sha} while draining, deferring the deploy")
        return

    lock = connection.lock(
        DEPLOY_LOCK_NAME, timeout=deploy_lock_timeout(checkout_path=checkout_path), blocking_timeout=0
    )
    if not lock.acquire(blocking=False):
        logger.info("Another deploy is already running, skipping this cycle")
        return

    try:
        logger.info(f"Deploying origin/master {sha}")
        succeeded = await run_deploy(checkout_path=checkout_path, sha=sha)
    finally:
        lock.release()

    state.last_deploy_at = time.time()
    if succeeded:
        state.last_deployed_sha = sha
        state.last_failed_sha = None
        state.last_error = None
        logger.info(f"Deploy of {sha} finished")
    else:
        state.last_failed_sha = sha
        state.last_error = "deploy failed"
        logger.error(f"Deploy of {sha} failed, retrying after the minimum interval")
    save_state(path=state_path, state=state)

    if succeeded:
        await recreate_deployer(checkout_path=checkout_path)
