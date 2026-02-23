from demetra.services.linear import get_linear_task as _get_linear_task
from demetra.services.tui import print_message


async def get_linear_task(project_name: str):
    print_message("Retrieving latest linear task", style="heading")
    task = await _get_linear_task(project_name=project_name)
    if not task:
        print_message("No TODO tasks found", style="error")
        return None
    print_message(f"Retrieved task: {task.identifier} - {task.title}", style="result")
    return task
