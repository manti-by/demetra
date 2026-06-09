import asyncio
import logging.config
import os
import sys

from rq.job import Job

from demetra.library.models import LinearTask
from demetra.services.database import (
    get_pending_session_task_ids,
    get_session,
    increment_run_attempts,
    upsert_pending_session,
)
from demetra.services.linear import post_comment, update_ticket_status
from demetra.services.queue import queue
from demetra.services.utils import log_stream
from demetra.settings import BASE_PATH, DEFAULT_USER_ID, LINEAR, LOG_DIR, LOGGING, MAX_RUN_ATTEMPTS


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)

TIMEOUT = 60 * 60


async def run_workflow(project_name: str, task_id: str) -> bool:
    if not task_id:
        logger.error(f"Task ID is empty: {task_id}")
        return False

    attempts = await increment_run_attempts(task_id)
    session = await get_session(task_id)
    if session and attempts > MAX_RUN_ATTEMPTS:
        logger.warning(f"Max run attempts ({MAX_RUN_ATTEMPTS}) reached for task {task_id}, moving to Awaiting Input")
        await post_comment(task_id=task_id, body="Max run attempts reached")
        await update_ticket_status(task_id=task_id, state_id=LINEAR["states"]["awaiting_input"])
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

    return False


async def delay_run_workflow(project_name: str, task_id: str) -> Job:
    return queue.enqueue(run_workflow, project_name=project_name, task_id=task_id)


async def process_tasks(tasks: list[LinearTask]) -> None:
    pending_ids = await get_pending_session_task_ids()
    logger.info(f"Processing {len(tasks)} TODO tasks ({len(pending_ids)} pending)")

    for task in tasks:
        if not task.project_name:
            logger.warning(f"Received task without project name: {task.full_title}")
            continue

        if task.id not in pending_ids:
            user_id = task.user_id or DEFAULT_USER_ID
            if not task.project_id or not user_id:
                logger.warning(f"Skipping task {task.id}: missing project_id={task.project_id}, user_id={user_id}")
                continue
            await upsert_pending_session(
                task_id=task.id,
                session_id=None,
                project_id=task.project_id,
                user_id=user_id,
                name=task.full_title,
            )

        logger.info(f"Starting workflow for {task.project_name} (task: {task.id})")
        await delay_run_workflow(project_name=task.project_name, task_id=task.id)
