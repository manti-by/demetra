import logging

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue, Retry
from rq.exceptions import InvalidJobOperation, NoSuchJobError
from rq.job import Job, JobStatus
from rq.registry import StartedJobRegistry
from rq.utils import as_text, current_timestamp

from demetra.settings import REDIS_URL, SUBPROCESS_TIMEOUT


logger = logging.getLogger(__name__)

connection = Redis.from_url(url=REDIS_URL)
queue = Queue(connection=connection, default_timeout=SUBPROCESS_TIMEOUT)

WORKFLOW_JOB_PATH = "demetra.services.daemons.watcher.run_workflow"

WORKFLOW_RETRIES = 1

REMOVE_EXPIRED_MEMBERS_SCRIPT = """
local now = tonumber(ARGV[1])
local removed = {}
for index, member in ipairs(ARGV) do
    if index > 1 then
        local score = redis.call('ZSCORE', KEYS[1], member)
        if score and tonumber(score) <= now then
            redis.call('ZREM', KEYS[1], member)
            table.insert(removed, member)
        end
    end
end
return removed
"""


def enqueue_workflow(*, project_name: str, task_id: str) -> Job:
    """Enqueue a workflow run for a task.

    The job is enqueued by import path so the API layer does not import the
    daemon module (and its logging configuration) at request time. Both the
    Linear watcher and chat-mode creation go through this single entry point.

    A workflow gets one RQ retry so the worker's own registry cleanup requeues
    a job abandoned by a killed worker instead of moving it to the failed
    registry first. Genuine failures still end up failed after that retry;
    :func:`requeue_abandoned_jobs` only handles entries cleanup has not taken.

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
    """Requeue started jobs whose worker heartbeat has expired.

    A worker killed by the deploy watchdog leaves its job in the started-job
    registry with a stale expiry. Workflow jobs carry one RQ retry, so the
    worker's own registry cleanup requeues such a job instead of failing it;
    recovery here covers the window before any worker runs that cleanup, and
    the two paths share the same retry policy.

    ``StartedJobRegistry.requeue()`` cannot be used here: in rq 2.10 the
    registry stores ``{job_id}:{execution_id}`` members and that helper removes
    only the bare job id, so it always raises ``InvalidJobOperation``.
    ``remove_executions()`` is no better: it resolves members through the
    execution registry, whose entries outlive the started score, so it misses
    the very member that needs removing. The raw expired members are claimed
    from the started registry itself instead.

    Scores are read in one snapshot, which supplies both the expired members
    and the ids with a fresh execution. A Lua script then removes only members
    whose score is still expired at removal time: a heartbeat renewing a member
    between the snapshot and the removal keeps it in the registry, so a job
    that is still running never loses its started-registry entry. A member is
    claimed before its job is enqueued, preventing RQ's cleanup from failing
    that job in between, and is restored with its original score when the
    enqueue fails so the next cycle can retry.

    A job that is no longer ``started``, or that has a fresh registry member
    from a worker that picked it up again, has already been moved on: its stale
    member is claimed without queueing the workflow a second time. A member
    expiring at exactly ``now`` counts as expired, not active.

    Returns:
        list[str]: The ids that were requeued.
    """
    try:
        registry = StartedJobRegistry(queue=queue, connection=connection)
        now = current_timestamp()
        snapshot = connection.zrange(name=registry.key, start=0, end=-1, withscores=True)
    except (RedisError, OSError, ValueError) as e:
        logger.warning(f"Failed to read the abandoned jobs: {e}")
        return []

    scores: dict[str | bytes, float] = {}
    active_job_ids: set[str] = set()
    for member, score in snapshot:
        if not isinstance(member, (str, bytes)):
            continue
        try:
            expiry = float(score)
        except (TypeError, ValueError):
            continue
        if expiry > now:
            try:
                active_job_ids.add(registry.parse_job_id(entry=as_text(member)))
            except ValueError:
                continue
        else:
            scores[member] = expiry

    candidates: list[tuple[str | bytes, str, Job | None]] = []
    for member in scores:
        try:
            job_id = registry.parse_job_id(entry=as_text(member))
        except ValueError:
            logger.warning(f"Ignoring an unparseable started-job registry entry: {member!r}")
            continue
        try:
            job = Job.fetch(id=job_id, connection=connection)
        except NoSuchJobError:
            candidates.append((member, job_id, None))
            continue
        except (RedisError, OSError, ValueError) as e:
            logger.warning(f"Failed to read the abandoned job {job_id}: {e}")
            continue
        if job.get_status() != JobStatus.STARTED or job_id in active_job_ids:
            candidates.append((member, job_id, None))
            continue
        candidates.append((member, job_id, job))

    if not candidates:
        return []

    try:
        claimed = set(
            connection.eval(
                REMOVE_EXPIRED_MEMBERS_SCRIPT, 1, registry.key, now, *(member for member, _, _ in candidates)
            )
        )
    except (RedisError, OSError, ValueError) as e:
        logger.warning(f"Failed to claim the abandoned jobs: {e}")
        return []

    requeued: list[str] = []
    for member, job_id, job in candidates:
        if member not in claimed or job is None:
            continue
        try:
            job.started_at = None
            job.ended_at = None
            job._exc_info = ""
            job.save()
            queue.enqueue_job(job)
        except (InvalidJobOperation, ValueError, RedisError, OSError) as e:
            logger.warning(f"Failed to requeue the abandoned job {job_id}: {e}")
            try:
                connection.zadd(registry.key, {as_text(member): scores[member]})
            except (RedisError, OSError) as restore_error:
                logger.warning(f"Failed to restore the abandoned job member {member!r}: {restore_error}")
            continue
        requeued.append(job_id)
    return requeued
