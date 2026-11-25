"""Deploy daemon — deploy origin/master once its CI passed, swapping worker generations.

Follow-up: MNT-316 — merge the watcher, the listener and the deploy daemon into
one universal watcher.
"""

import json
import logging
import os
import shlex
import time
from pathlib import Path

from redis.lock import Lock

from demetra.library.models import DeployState
from demetra.services.daemons.deploy_support import compose_command, default_state_path, load_state, save_state
from demetra.services.daemons.worker_swap import SWAP_STEP_BUDGET, maintain_workers, swap_workers
from demetra.services.persistence.queue import connection
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

MIGRATE_STEP = "migrate"

SETPRIV_COMMAND = "setpriv"

DEPLOY_IMAGE = "mantiby/demetra:latest"

IMAGE_REVISION_LABEL = "org.opencontainers.image.revision"

NO_LABEL_VALUE = "<no value>"

DEPLOY_SERVICE = "deployer"

DOCKER_SOCKET = "/var/run/docker.sock"

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


def combine_check_run_pages(pages: list) -> dict:
    """Merge the slurped pages of a paginated check-runs response into one payload.

    The endpoint returns 30 runs per page, so a commit with more checks would
    otherwise be judged on its first page alone and a failing or pending check
    on a later page could be truncated away.

    Args:
        pages: The decoded ``gh api --paginate --slurp`` output, one mapping per page.

    Returns:
        dict: A single payload carrying the check runs of every page.
    """
    runs = []
    for page in pages:
        if isinstance(page, dict):
            runs.extend(page.get("check_runs") or [])
    return {"check_runs": runs}


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


def build_deploy_steps(checkout_path: Path, sha: str | None = None) -> list[tuple[str, list[str]]]:
    """Build the ordered deploy commands for the host checkout.

    Mirrors the ``deploy`` target in the Makefile. The ``up`` step recreates
    only the non-worker services: the workers are swapped separately by
    :func:`swap_workers`, which starts the new generation before signalling the
    old one. The ``deployer`` service is deliberately absent from the ``up``
    list: the daemon must not recreate itself while it runs the deploy. The
    pull runs as the checkout owner so the new objects and files keep the host
    user's ownership. Every command names
    the checkout explicitly (``--project-directory`` for compose, an absolute
    build context) so the daemon never depends on its own working directory,
    which is the image-owned module root rather than the writable checkout.

    The built image is labelled with the gated commit, so the running
    containers record which commit actually shipped even after the state file
    is lost, and a failed deploy is never mistaken for a successful one.

    Args:
        checkout_path: The host checkout the daemon deploys.
        sha: The gated commit to stamp on the built image, omitted when the
            caller only needs the command shape (e.g. the lock TTL).

    Returns:
        list[tuple[str, list[str]]]: The step name and command pairs.
    """
    docker = str(DEPLOY["docker_path"])
    git = str(DEPLOY["git_path"])
    checkout = str(checkout_path)
    compose = compose_command(checkout_path=checkout_path)
    owner = checkout_owner_prefix(checkout_path=checkout_path)
    build = [docker, "build", "--platform", "linux/amd64", "--tag", DEPLOY_IMAGE]
    if sha:
        build += ["--label", f"{IMAGE_REVISION_LABEL}={sha}"]
    steps = [
        (PULL_STEP, [*owner, git, "-c", f"safe.directory={checkout_path}", "pull", "--ff-only"]),
        ("build", [*build, checkout]),
        ("pull_images", [*compose, "pull", "postgres", "redis", "react-build"]),
        (MIGRATE_STEP, [*compose, "up", "--abort-on-container-failure", "migrate", "react-build"]),
        ("up", [*compose, "up", "--detach", "--force-recreate", "--no-deps", *DEPLOY["compose_services"]]),
    ]
    if reload_command := shlex.split(DEPLOY["nginx_reload_command"]):
        steps.append(("nginx_reload", reload_command))
    return steps


def deploy_lock_timeout(checkout_path: Path) -> int:
    """Return a lock TTL that covers a whole multi-step deploy.

    Every step is bounded by ``step_timeout``, and so is every command of the
    worker swap and maintenance that run under the same lock. The post-pull
    HEAD read is bounded by ``step_timeout`` too but is not a step, so it is
    budgeted separately; the resulting slack also covers the state writes. A
    shorter TTL would let the lock expire mid-deploy and allow a second daemon
    to start a concurrent one.

    Args:
        checkout_path: The host checkout the daemon deploys.

    Returns:
        int: The lock TTL in seconds.
    """
    steps = len(build_deploy_steps(checkout_path=checkout_path))
    return (steps + 1 + SWAP_STEP_BUDGET) * DEPLOY["step_timeout"]


def acquire_deploy_lock(*, checkout_path: Path, blocking: bool) -> Lock | None:
    """Take the shared deploy lock, the same one the manual ``make deploy`` path takes.

    Serializing both paths matters because they mutate the same checkout and
    rebuild the same image tag: a manual ``git pull`` landing between the
    daemon's CI gate and its own pull would make the daemon build a commit
    whose checks it never read.

    Args:
        checkout_path: The host checkout the daemon deploys.
        blocking: Whether to wait for a running deploy instead of giving up.

    Returns:
        Lock | None: The acquired lock, or None when it is already held.
    """
    timeout = deploy_lock_timeout(checkout_path=checkout_path)
    lock = connection.lock(DEPLOY_LOCK_NAME, timeout=timeout, blocking_timeout=timeout if blocking else 0)
    return lock if lock.acquire(blocking=blocking) else None


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

    The read is bounded by ``step_timeout`` because it runs under the deploy
    lock, whose TTL budgets one step for it; the default subprocess timeout
    would let it outlive the lease.

    Args:
        checkout_path: The host checkout the daemon deploys.

    Returns:
        str | None: The checked-out commit sha, or None when the command fails.
    """
    git = str(DEPLOY["git_path"])
    command = [*checkout_owner_prefix(checkout_path=checkout_path)]
    command += [git, "-c", f"safe.directory={checkout_path}", "rev-parse", "HEAD"]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=checkout_path, disable_stdio=True, timeout=DEPLOY["step_timeout"]
    )
    if exit_code != 0:
        logger.error(f"Failed to read the checked-out commit: {stderr.strip()}")
        return None
    return stdout.strip() or None


async def get_running_revision(checkout_path: Path) -> str | None:
    """Read the commit label of this stack's running api container.

    This is the only trustworthy record of what is actually deployed: the
    checkout can sit at a newer commit whose build failed, and the state file
    can be lost or reset. The container is resolved through Compose, so a
    same-named ``api`` service of another project on the same Docker daemon is
    never mistaken for this checkout's one.

    Args:
        checkout_path: The host checkout the daemon deploys.

    Returns:
        str | None: The label value, or None when no labelled container runs.
    """
    exit_code, stdout, stderr = await run_command(
        command=[*compose_command(checkout_path=checkout_path), "ps", "-q", "api"],
        target_path=checkout_path,
        disable_stdio=True,
        timeout=DEPLOY["step_timeout"],
    )
    if exit_code != 0:
        logger.warning(f"Failed to resolve the running api container: {stderr.strip()}")
        return None
    containers = stdout.split()
    if not containers:
        return None

    command = [
        str(DEPLOY["docker_path"]),
        "inspect",
        "--format",
        f'{{{{index .Config.Labels "{IMAGE_REVISION_LABEL}"}}}}',
        containers[0],
    ]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=checkout_path, disable_stdio=True, timeout=DEPLOY["step_timeout"]
    )
    if exit_code != 0:
        logger.warning(f"Failed to read the running image revision: {stderr.strip()}")
        return None
    revision = stdout.strip()
    return revision if revision and revision != NO_LABEL_VALUE else None


async def checkout_has_no_local_changes(checkout_path: Path) -> bool:
    """Confirm the checkout holds no change that CI never checked.

    ``git pull --ff-only`` preserves uncommitted tracked modifications, and an
    untracked file in the build context is copied into the image, so a HEAD
    comparison alone would let untested content reach the containers. Ignored
    files (``.keys/``, ``.env*``, ``node_modules``) never show up here, so the
    check only trips on content that would actually ship.

    Args:
        checkout_path: The host checkout the daemon deploys.

    Returns:
        bool: True when the working tree matches the checked-out commit.
    """
    git = str(DEPLOY["git_path"])
    command = [*checkout_owner_prefix(checkout_path=checkout_path)]
    command += [git, "-c", f"safe.directory={checkout_path}", "status", "--porcelain"]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=checkout_path, disable_stdio=True, timeout=DEPLOY["step_timeout"]
    )
    if exit_code != 0:
        logger.error(f"Failed to read the checkout status: {stderr.strip()}")
        return False
    if stdout.strip():
        logger.error(f"Checkout has changes that CI never checked, aborting the deploy: {stdout.strip()}")
        return False
    return True


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
    record a failure for a commit that may well be green. Every page is read,
    so a failing check beyond the first 30 runs still blocks the deploy.

    Args:
        sha: The commit to inspect.
        repository: The ``owner/repo`` slug owning the commit.

    Returns:
        str: ``"passed"``, ``"pending"``, ``"failed"`` or ``"unknown"`` when
            the status could not be read.
    """
    command = [
        str(DEPLOY["github_path"]),
        "api",
        "--paginate",
        "--slurp",
        f"repos/{repository}/commits/{sha}/check-runs",
    ]
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
    if isinstance(payload, list):
        payload = combine_check_run_pages(pages=payload)
    if not isinstance(payload, dict):
        logger.warning(f"Unexpected check runs payload for {sha}: {type(payload).__name__}")
        return CI_STATUS_UNKNOWN
    return summarize_check_runs(payload=payload)


async def run_deploy_step(name: str, command: list[str], checkout_path: Path) -> bool:
    """Run one deploy command and log its outcome.

    A process-start error (e.g. a missing reload executable) is reported as a
    failed step rather than raised: an exception would escape the step loop and
    skip the deployment timestamp, so the next poll would repeat the build and
    the migration without the minimum interval.

    Args:
        name: The step name used in the log lines.
        command: The command to run.
        checkout_path: Working directory of the command.

    Returns:
        bool: True when the command exited with a zero code.
    """
    logger.info(f"Deploy step '{name}' started: {' '.join(command)}")
    try:
        exit_code, stdout, stderr = await run_command(
            command=command, target_path=checkout_path, timeout=DEPLOY["step_timeout"]
        )
    except OSError as e:
        logger.error(f"Deploy step '{name}' could not be started: {e}")
        return False
    if exit_code != 0:
        output = stderr.strip() or stdout.strip()
        logger.error(f"Deploy step '{name}' failed with exit code {exit_code}: {output[-LOG_TAIL_CHARS:]}")
        return False
    logger.info(f"Deploy step '{name}' succeeded")
    return True


async def checkout_matches_sha(checkout_path: Path, sha: str) -> bool:
    """Confirm the checkout still holds the commit whose CI passed, unchanged.

    ``git pull --ff-only`` fast-forwards to whatever ``origin/master`` points
    to at pull time, so master can advance between the gate check and the pull.
    Building that newer commit would ship code whose CI was never checked, so
    the deploy aborts and the next cycle gates the new commit instead. HEAD
    alone is not enough: the pull keeps uncommitted tracked changes, so the
    working tree is checked too.

    Args:
        checkout_path: The host checkout the daemon deploys.
        sha: The gated commit the deploy is allowed to build.

    Returns:
        bool: True when the checkout is at the gated commit with a clean tree.
    """
    head_sha = await get_checkout_head_sha(checkout_path=checkout_path)
    if head_sha != sha:
        logger.error(f"Checkout is at {head_sha} instead of the gated commit {sha}, aborting the deploy")
        return False
    return await checkout_has_no_local_changes(checkout_path=checkout_path)


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


async def request_deployer_recreate(state: DeployState, state_path: Path, checkout_path: Path) -> None:
    """Recreate the deployer container, keeping the request pending until it is dispatched.

    The flag is cleared before the helper starts because a successful dispatch
    kills this process, so a flag cleared afterwards would be persisted only
    sometimes and the next daemon would recreate itself again, forever. A
    helper that cannot be started restores the flag, and the next poll retries
    the recreate on its own instead of waiting for another commit.

    Args:
        state: The deploy state to update.
        state_path: The JSON state file path.
        checkout_path: The host checkout the daemon deploys.
    """
    state.pending_recreate = False
    save_state(path=state_path, state=state)
    if await recreate_deployer(checkout_path=checkout_path):
        return
    state.pending_recreate = True
    save_state(path=state_path, state=state)
    logger.error("Deployer container recreate failed, retrying on the next poll")


async def run_deploy(checkout_path: Path, sha: str, state_path: Path, state: DeployState) -> bool:
    """Run the deploy steps in order, stopping at the first required failure.

    The image pull and the nginx reload are optional: the Makefile tolerates a
    failed pull, and a failed reload leaves the previous nginx configuration
    serving, which does not invalidate the containers that were already
    recreated. Treating the reload as required would retry the whole
    destructive sequence, migrations included, every minimum interval.

    After the migration the worker generations are swapped: staging starts on
    the new image, and the live generation is signalled once to drain the
    workflow it holds. No deploy waits for a queue to empty, so a job that
    started after the CI gate is finished on the old image instead of killed.

    Args:
        checkout_path: The host checkout the daemon deploys.
        sha: The gated commit the deploy is allowed to build.
        state_path: The JSON deploy state file path.
        state: The deploy state, updated with the new worker generation.

    Returns:
        bool: True when every required step succeeded.
    """
    for name, command in build_deploy_steps(checkout_path=checkout_path, sha=sha):
        succeeded = await run_deploy_step(name=name, command=command, checkout_path=checkout_path)
        if not succeeded:
            if name in OPTIONAL_STEPS:
                logger.warning(f"Deploy step '{name}' failed, continuing with the deploy")
                continue
            logger.error(f"Deploy aborted at step '{name}'")
            return False
        if name == PULL_STEP and not await checkout_matches_sha(checkout_path=checkout_path, sha=sha):
            return False
        if name == MIGRATE_STEP and not await swap_workers(
            checkout_path=checkout_path, state_path=state_path, state=state
        ):
            logger.error("Deploy aborted at the worker swap")
            return False
    return True


async def run_deploy_cycle() -> None:
    """Run one deploy poll: reap workers, gate on CI and swap the live generation.

    Drained workers are reaped and hung ones escalated at the start of every
    cycle, under the same Redis lock the deploy takes. The remote commit is
    re-read after the CI gate so a push that landed while checking is left to
    the next cycle instead of deploying stale code. A single Redis lock, kept
    for the length of the whole deploy, keeps one deploy at a time even if two
    daemon containers overlap. The deployer is
    recreated from the new image only after a successful deploy, once the state
    is persisted and the lock is released, so the replacement daemon does not
    start deployed-blind or blocked by its own lock.

    The deployment identity is recovered from the running api image, not from
    the checkout: a failed build leaves the checkout on a newer commit whose
    containers were never recreated, and seeding that commit would skip it
    forever. A deferred recreate is retried at the start of every cycle, so a
    failed self-recreate is not lost once the deploy is recorded as successful.
    """
    checkout_path = DEPLOY["host_checkout"]
    state_path = default_state_path()
    maintenance_lock = acquire_deploy_lock(checkout_path=checkout_path, blocking=False)
    if maintenance_lock is None:
        logger.debug("Another deploy holds the lock, skipping worker maintenance")
    else:
        try:
            await maintain_workers(checkout_path=checkout_path, state_path=state_path)
        finally:
            maintenance_lock.release()
    state = load_state(path=state_path)

    if state.pending_recreate:
        logger.info("Retrying the deferred deployer container recreate")
        await request_deployer_recreate(state=state, state_path=state_path, checkout_path=checkout_path)

    sha = await get_remote_master_sha(checkout_path=checkout_path)
    if not sha:
        return

    if not state.last_deployed_sha:
        running_sha = await get_running_revision(checkout_path=checkout_path)
        if running_sha:
            state.last_deployed_sha = running_sha
            save_state(path=state_path, state=state)
            logger.info(f"Seeded the deploy state from the running api image revision {running_sha}")
        else:
            logger.info("No deployed revision found, leaving origin/master eligible for a deploy")

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

    current_sha = await get_remote_master_sha(checkout_path=checkout_path)
    if current_sha != sha:
        logger.info(f"origin/master moved to {current_sha} while checking CI, deferring the deploy")
        return

    lock = acquire_deploy_lock(checkout_path=checkout_path, blocking=False)
    if lock is None:
        logger.info("Another deploy is already running, skipping this cycle")
        return

    try:
        # Another deploy may have committed this commit between the checks above
        # and the lock: reloading here is what makes the lock, and not the poll
        # order, decide whether the commit still needs a deploy.
        state = load_state(path=state_path)
        if not should_deploy(state=state, sha=sha, now=time.time()):
            logger.info(f"Deploy of {sha} is already recorded, skipping this cycle")
            return
        logger.info(f"Deploying origin/master {sha}")
        succeeded = await run_deploy(checkout_path=checkout_path, sha=sha, state_path=state_path, state=state)
        state.last_deploy_at = time.time()
        if succeeded:
            state.last_deployed_sha = sha
            state.last_failed_sha = None
            state.last_error = None
            state.pending_recreate = True
            logger.info(f"Deploy of {sha} finished")
        else:
            state.last_failed_sha = sha
            state.last_error = "deploy failed"
            logger.error(f"Deploy of {sha} failed, retrying after the minimum interval")
        save_state(path=state_path, state=state)
    finally:
        lock.release()

    if state.pending_recreate:
        await request_deployer_recreate(state=state, state_path=state_path, checkout_path=checkout_path)
