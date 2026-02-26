import asyncio
import logging
import sys

from demetra.services.database import (
    add_pending_task,
    get_pending_task_ids,
    mark_task_failed,
    mark_task_processed,
)
from demetra.settings import BASE_PATH


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TIMEOUT = 600


async def run_workflow(project_name: str, task_id: str) -> bool:
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(BASE_PATH / "main.py"),
            "--project-name",
            project_name,
            "--task-id",
            task_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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

    except (RuntimeError, OSError) as e:
        logger.error(f"Process creation/execution error for task {task_id}: {e}")

    return False


async def process_tasks(tasks: list) -> None:
    pending_ids = await get_pending_task_ids()
    logger.info(f"Processing {len(tasks)} TODO tasks ({len(pending_ids)} pending)")

    for task, project_name in tasks:
        if task.id not in pending_ids:
            await add_pending_task(task_id=task.id, project_name=project_name)

        logger.info(f"Starting workflow for {project_name} (task: {task.id})")
        if await run_workflow(project_name=project_name, task_id=task.id):
            await mark_task_processed(task_id=task.id)
        else:
            await mark_task_failed(task_id=task.id)
