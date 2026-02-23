from demetra.models import Context
from demetra.services.database import get_session
from demetra.services.filesystem import get_project_root
from demetra.services.git import git_worktree_create
from demetra.services.linear import get_linear_task
from demetra.services.tui import print_message


async def setup_workflow(project_name: str, auto_mode: bool) -> Context | None:
    project_path = get_project_root(project_name=project_name)
    print_message(f"Project root: {project_path}", style="result")

    print_message("Retrieving latest linear task", style="heading")
    linear_task = await get_linear_task(project_name=project_name)
    if not linear_task:
        return None
    print_message(f"Retrieved task: {linear_task.identifier} - {linear_task.title}", style="result")

    session = await get_session(task_id=linear_task.id)

    branch_name = f"demetra/{linear_task.slug}"
    print_message("Creating feature worktree", style="heading")
    print_message("")
    worktree_path = await git_worktree_create(target_path=project_path, branch_name=branch_name)
    print_message("")
    print_message(f"Created worktree at: {worktree_path}", style="result")

    return Context(
        project_name=project_name,
        auto_mode=auto_mode,
        linear_task=linear_task,
        branch_name=branch_name,
        project_path=project_path,
        worktree_path=worktree_path,
        session=session,
    )
