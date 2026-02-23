from pathlib import Path

from demetra.services.linear import (
    get_linear_task as _get_linear_task,
    linear_cleanup as _linear_cleanup,
    post_comment as _post_comment,
    update_ticket_status as _update_ticket_status,
)
from demetra.services.tui import print_message


async def get_linear_task(project_name: str):
    print_message("Retrieving latest linear task", style="heading")
    task = await _get_linear_task(project_name=project_name)
    if not task:
        print_message("No TODO tasks found", style="error")
        return None
    print_message(f"Retrieved task: {task.identifier} - {task.title}", style="result")
    return task


async def update_ticket_status(task_id: str, state_id: str):
    await _update_ticket_status(task_id=task_id, state_id=state_id)


async def post_comment(task_id: str, body: str):
    await _post_comment(task_id=task_id, body=body)


async def linear_cleanup(task_id: str, is_error: bool):
    await _linear_cleanup(task_id=task_id, is_error=is_error)
