import logging

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from rq.job import Job
from rq.registry import StartedJobRegistry
from rq.utils import current_timestamp

from demetra.settings import REDIS_URL, SUBPROCESS_TIMEOUT


logger = logging.getLogger(__name__)

connection = Redis.from_url(url=REDIS_URL)
queue = Queue(connection=connection, default_timeout=SUBPROCESS_TIMEOUT + 60)  # Overhead for RQ itself

WORKFLOW_JOB_PATH = "demetra.services.daemons.watcher.run_workflow"


def enqueue_workflow(*, project_name: str, task_id: str) -> Job:
    """Enqueue a workflow run for a task.

    The job is enqueued by import path so the API layer does not import the
    daemon module (and its logging configuration) at request time. Both the
    Linear watcher and chat-mode creation go through this single entry point.

    Args:
        project_name: The name of the project the task belongs to.
        task_id: The task identifier.

    Returns:
        Job: The enqueued RQ job.
    """
    return queue.enqueue(WORKFLOW_JOB_PATH, project_name=project_name, task_id=task_id)


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
