import json
import logging

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue, Retry
from rq.job import Job
from rq.registry import StartedJobRegistry
from rq.utils import current_timestamp

from demetra.settings import PENDING_COMMENTS_TTL, REDIS_URL, SUBPROCESS_TIMEOUT


logger = logging.getLogger(__name__)

connection = Redis.from_url(url=REDIS_URL)
queue = Queue(connection=connection, default_timeout=SUBPROCESS_TIMEOUT)

WORKFLOW_JOB_PATH = "demetra.services.daemons.watcher.run_workflow"

WORKFLOW_RETRIES = 1

PENDING_COMMENTS_KEY_PREFIX = "demetra:pending-comments:"


def _pending_comments_key(task_id: str) -> str:
    """Return the Redis key holding the pending CodeRabbit batch of a task.

    Args:
        task_id: The task identifier.

    Returns:
        str: The namespaced Redis key.
    """
    return f"{PENDING_COMMENTS_KEY_PREFIX}{task_id}"


def save_pending_comments(task_id: str, comments: dict) -> bool | None:
    """Store one batch of CodeRabbit comments for a task.

    The write is conditional so notifications arriving while a batch is being
    processed cannot enqueue a second workflow.

    Args:
        task_id: The task identifier.
        comments: The batch payload to serialize as JSON.

    Returns:
        bool | None: True when stored, False when a batch is already pending,
            None when Redis or serialization failed.
    """
    try:
        saved = connection.set(
            name=_pending_comments_key(task_id), value=json.dumps(comments), nx=True, ex=PENDING_COMMENTS_TTL
        )
    except (RedisError, OSError, TypeError) as e:
        logger.warning(f"Failed to save pending comments for {task_id}: {e}")
        return None
    if saved is True:
        return True
    if saved is None or saved is False:
        return False
    logger.warning(f"Unexpected Redis response saving pending comments for {task_id}: {saved!r}")
    return None


def load_pending_comments(task_id: str) -> dict | None:
    """Load the pending CodeRabbit batch for a task.

    Args:
        task_id: The task identifier.

    Returns:
        dict | None: The parsed payload, or None when missing, corrupt or the
            broker is unreachable.
    """
    try:
        raw = connection.get(name=_pending_comments_key(task_id))
    except (RedisError, OSError) as e:
        logger.warning(f"Failed to load pending comments for {task_id}: {e}")
        return None
    if raw is None:
        return None
    if isinstance(raw, bytes):
        try:
            raw = raw.decode()
        except UnicodeDecodeError:
            logger.warning(f"Pending comments for {task_id} are not valid UTF-8")
            return None
    if not isinstance(raw, str):
        logger.warning(f"Unexpected pending comments payload for {task_id}: {raw!r}")
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"Pending comments for {task_id} are not valid JSON")
        return None
    if not isinstance(payload, dict):
        logger.warning(f"Unexpected pending comments payload for {task_id}: {payload!r}")
        return None
    return payload


def clear_pending_comments(task_id: str) -> None:
    """Remove the pending CodeRabbit batch of a task.

    Args:
        task_id: The task identifier.
    """
    try:
        connection.delete(_pending_comments_key(task_id))
    except (RedisError, OSError) as e:
        logger.warning(f"Failed to clear pending comments for {task_id}: {e}")


def enqueue_workflow(*, project_name: str, task_id: str) -> Job:
    """Enqueue a workflow run for a task.

    The job is enqueued by import path so the API layer does not import the
    daemon module (and its logging configuration) at request time. Both the
    Linear watcher and chat-mode creation go through this single entry point.

    A workflow gets one RQ retry so registry cleanup requeues a job abandoned
    by a killed worker instead of moving it to the failed registry first.
    Genuine failures still end up failed after that retry;
    :func:`requeue_abandoned_jobs` runs that same cleanup when no worker has
    done so yet.

    Args:
        project_name: The name of the project the task belongs to.
        task_id: The task identifier.

    Returns:
        Job: The enqueued RQ job.
    """
    return queue.enqueue(
        WORKFLOW_JOB_PATH, project_name=project_name, task_id=task_id, retry=Retry(max=WORKFLOW_RETRIES)
    )


def get_live_task_ids() -> list[str]:
    """Return the task ids of the workflow jobs that are currently running.

    A job is live while its execution sits in the queue's started-job registry,
    which RQ fills right before execution and empties on completion. Entries
    whose score — the execution expiry, refreshed by the worker's heartbeat
    while the job runs — is already in the past are skipped, so an entry left
    behind by a killed worker ages out of the result instead of being reported
    as live forever. Nothing is mutated: RQ's ``cleanup()``, which would move
    abandoned jobs to the failed registry, is deliberately not called from a
    read path.

    Returns:
        list[str]: The task ids of the running jobs, in registry order. Empty
            when nothing is running or the broker is unreachable.
    """
    try:
        registry = StartedJobRegistry(queue=queue, connection=connection)
        expired_job_ids = set(registry.get_expired_job_ids(current_timestamp()))
        job_ids = [job_id for job_id in registry.get_job_ids(cleanup=False) if job_id not in expired_job_ids]
        jobs = Job.fetch_many(job_ids=job_ids, connection=connection)
    except (RedisError, OSError) as e:
        logger.warning(f"Failed to read the running jobs: {e}")
        return []

    task_ids: list[str] = []
    for job in jobs:
        if job is None:
            continue
        task_id = job.kwargs.get("task_id")
        if isinstance(task_id, str) and task_id:
            task_ids.append(task_id)
    return task_ids


def requeue_abandoned_jobs() -> list[str]:
    """Recover started jobs whose worker heartbeat has expired.

    A worker killed by the deploy watchdog leaves its job in the started-job
    registry with a stale expiry. Recovery goes through RQ's own
    ``StartedJobRegistry.cleanup()``, the same path a worker's registry cleanup
    takes, instead of a second claim-and-enqueue implementation. Both paths
    then check and spend the remaining retry inside the pipeline that enqueues
    the job, so a retry already prepared by one cleanup cannot be duplicated by
    a separate enqueue here. Jobs with no retry left are failed by RQ rather
    than admitted again, and jobs enqueued before retries were configured have
    no budget to reset and are failed the same way.

    The registry entry and the retry are committed in one pipeline, so a
    heartbeat renewed between reading the expired ids and cleaning up keeps
    its entry and the job keeps running. Broker failures are contained here so
    maintenance still saves the rest of its state on this poll.

    Returns:
        list[str]: The ids whose registry entries had expired when this ran.
    """
    try:
        registry = StartedJobRegistry(queue=queue, connection=connection)
        now = current_timestamp()
        expired_job_ids = registry.get_expired_job_ids(timestamp=now)
        if expired_job_ids:
            registry.cleanup(timestamp=now)
    except (RedisError, OSError, ValueError) as e:
        logger.warning(f"Failed to recover the abandoned jobs: {e}")
        return []
    return expired_job_ids
