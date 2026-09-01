import asyncio
import logging.config
import os
import sys

from rq.job import Job

from demetra.library.models import LinearTask
from demetra.services.linear import get_linear_config_value, post_comment, update_ticket_status
from demetra.services.persistence.database import (
    get_pending_session_task_ids,
    get_session,
    increment_run_attempts,
    upsert_pending_session,
)
from demetra.services.persistence.queue import queue
from demetra.services.runtime.utils import log_stream
from demetra.settings import BASE_PATH, DEFAULT_USER_ID, LOG_DIR, LOGGING, MAX_RUN_ATTEMPTS


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)

TIMEOUT = 60 * 60


async def run_workflow(project_name: str, task_id: str) -> bool:
    """Run the main workflow for a task as a subprocess.

    Enforces the run-attempt limit, spawns ``main.py`` with the project name
    and task id, streams its logs, and increments the run-attempt counter on
    failure. Tasks that exceed the limit are moved to Awaiting Input.

    Args:
        project_name: The name of the project the task belongs to.
        task_id: The Linear task identifier.

    Returns:
        bool: True when the workflow completed successfully.
    """
    if not task_id:
        logger.error(f"Task ID is empty: {task_id}")
        return False

    session = await get_session(task_id)
    user_id = session.user_id if session else DEFAULT_USER_ID
    if session and session.run_attempts > MAX_RUN_ATTEMPTS:
        logger.warning(f"Max run attempts ({MAX_RUN_ATTEMPTS}) reached for task {task_id}, moving to Awaiting Input")
        await post_comment(task_id=task_id, body="Max run attempts reached")
        state_id = await get_linear_config_value(name="awaiting_input", user_id=user_id)
        if state_id:
            await update_ticket_status(task_id=task_id, state_id=state_id)
        else:
            logger.error("Linear state 'awaiting_input' is not configured")
        return False

    process = None
    try:
        env = os.environ.copy()
        log_path = LOG_DIR / f"sessions/{task_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        env["LOG_PATH"] = str(log_path)

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(BASE_PATH / "main.py"),
            "--project-name",
            project_name,
            "--task-id",
            task_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(BASE_PATH),
        )

        if process.stdout and process.stderr:
            await asyncio.gather(
                log_stream(process.stdout, logger_callable=logger.info),
                log_stream(process.stderr, logger_callable=logger.error),
            )

        _, stderr = await asyncio.wait_for(process.communicate(), timeout=TIMEOUT)
        if process.returncode == 0:
            logger.info(f"Workflow completed successfully for task: {task_id}")
            return True

        logger.error(f"Workflow failed for task {task_id}: {stderr.decode()}")

    except TimeoutError:
        logger.error(f"Workflow timed out for task {task_id} after {TIMEOUT}s")
        if process:
            process.kill()
            await process.wait()

    except (RuntimeError, OSError) as e:
        logger.error(f"Process creation/execution error for task {task_id}: {e}")

    attempts = await increment_run_attempts(task_id)
    if attempts > MAX_RUN_ATTEMPTS:
        logger.warning(f"Max run attempts ({MAX_RUN_ATTEMPTS}) reached for task {task_id}, moving to Awaiting Input")
        await post_comment(task_id=task_id, body="Max run attempts reached")
        state_id = await get_linear_config_value(name="awaiting_input", user_id=user_id)
        if state_id:
            await update_ticket_status(task_id=task_id, state_id=state_id)
        else:
            logger.error("Linear state 'awaiting_input' is not configured")
        return False

    return False


async def delay_run_workflow(project_name: str, task_id: str) -> Job:
    """Enqueue a workflow run for a task on the RQ queue.

    Args:
        project_name: The name of the project the task belongs to.
        task_id: The Linear task identifier.

    Returns:
        Job: The enqueued RQ job.
    """
    return queue.enqueue(run_workflow, project_name=project_name, task_id=task_id)


async def process_tasks(tasks: list[LinearTask]) -> None:
    """Process a batch of TODO tasks, upserting sessions and queueing workflows.

    Tasks already pending keep their session; new tasks get a pending session
    row, are moved to ``in_progress`` in Linear and then have their workflow
    enqueued.

    Args:
        tasks: The TODO tasks to process.
    """
    pending_ids = await get_pending_session_task_ids()
    logger.info(f"Processing {len(tasks)} TODO tasks ({len(pending_ids)} pending)")

    for task in tasks:
        if not task.project_name:
            logger.warning(f"Received task without project name: {task.full_title}")
            continue

        user_id = task.user_id or DEFAULT_USER_ID
        if task.id not in pending_ids:
            if not task.project_id or not user_id:
                logger.warning(f"Skipping task {task.id}: missing project_id={task.project_id}, user_id={user_id}")
                continue
            await upsert_pending_session(
                task_id=task.id,
                session_id=None,
                project_id=task.project_id,
                user_id=user_id,
                name=task.full_title,
                linear_link=task.url,
            )

        # Always move an accepted TODO task to ``in_progress``, even on re-pickup:
        # a task can return to TODO while still pending (session_id="") after a
        # failed run, and update_ticket_status can fail transiently. Re-applying
        # the same state each poll is idempotent in Linear.
        state_id = await get_linear_config_value(name="in_progress", user_id=user_id)
        if state_id is None:
            logger.error(f"Linear state 'in_progress' is not configured for task {task.id}")
        elif not await update_ticket_status(task_id=task.id, state_id=state_id):
            logger.warning(f"Failed to move task {task.id} to 'in_progress'")

        logger.info(f"Starting workflow for {task.project_name} (task: {task.id})")
        await delay_run_workflow(project_name=task.project_name, task_id=task.id)
