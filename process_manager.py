#!/usr/bin/env python3
import asyncio
import logging
import sys

from demetra.services.database import (
    add_pending_task,
    get_pending_task_ids,
    get_task_status,
    init_db,
    mark_task_failed,
    mark_task_processed,
)
from demetra.services.linear import get_all_todo_issues
from demetra.settings import BASE_PATH


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = 300


async def run_workflow(project_name: str) -> bool:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(BASE_PATH / "main.py"),
        "--project-name",
        project_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _stdout, stderr = await process.communicate()
    if process.returncode == 0:
        logger.info(f"Workflow completed successfully for project: {project_name}")
        return True
    logger.error(f"Workflow failed for project {project_name}: {stderr.decode()}")
    return False


async def process_tasks(tasks: list, pending_ids: set[str]) -> None:
    for issue, project_name in tasks:
        task_id = issue.id
        if task_id in pending_ids:
            status = await get_task_status(task_id)
            if status in ("processed", "failed"):
                logger.debug(f"Skipping {task_id} - already {status}")
                continue
            logger.info(f"Task {task_id} already pending, skipping")
            continue

        await add_pending_task(task_id, project_name)
        logger.info(f"Starting workflow for {project_name} (task: {task_id})")

        success = await run_workflow(project_name)

        if success:
            await mark_task_processed(task_id)
        else:
            await mark_task_failed(task_id)


async def poll_loop() -> None:
    await init_db()
    logger.info("Process manager started, polling every 5 minutes")

    while True:
        try:
            logger.debug("Polling Linear API for TODO issues")
            tasks = await get_all_todo_issues()

            if not tasks:
                logger.debug("No TODO issues found")
            else:
                pending_ids = await get_pending_task_ids()
                logger.info(f"Found {len(tasks)} TODO issues, {len(pending_ids)} pending")
                await process_tasks(tasks, pending_ids)

        except (OSError, asyncio.CancelledError) as e:
            logger.error(f"Error polling Linear: {e}")

        await asyncio.sleep(POLL_INTERVAL)


async def main() -> None:
    await poll_loop()


if __name__ == "__main__":
    asyncio.run(main())
