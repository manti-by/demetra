from redis import Redis
from rq import Queue
from rq.job import Job

from demetra.settings import REDIS_URL


queue = Queue(connection=Redis.from_url(url=REDIS_URL), default_timeout=3600)

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
