import asyncio
import logging.config
import os
import sys

from rq.job import Job

from demetra.library.models import LinearTask
from demetra.services.database import (
    add_pending_task,
    get_pending_task_ids,
    mark_task_failed,
    mark_task_processed,
)
from demetra.services.queue import queue
from demetra.services.utils import log_stream
from demetra.settings import BASE_PATH, LOG_DIR, LOGGING


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)

TIMEOUT = 60 * 60


async def run_workflow(project_name: str, task_id: str) -> bool:
    if not task_id:
        logger.error(f"Task ID is empty: {task_id}")
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
    pending_ids = await get_pending_task_ids()
    logger.info(f"Processing {len(tasks)} TODO tasks ({len(pending_ids)} pending)")

    for task in tasks:
        if not task.project_name:
            logger.warning(f"Received task without project name: {task.full_title}")
            continue

        if task.id not in pending_ids:
            await add_pending_task(task_id=task.id, project_name=task.project_name, task_title=task.full_title)

        logger.info(f"Starting workflow for {task.project_name} (task: {task.id})")
        if await delay_run_workflow(project_name=task.project_name, task_id=task.id):
            await mark_task_processed(task_id=task.id)
        else:
            await mark_task_failed(task_id=task.id)
