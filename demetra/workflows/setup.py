from demetra.library.models import Context, Project
from demetra.services.database import get_project_environments, get_session, search_projects_by_name
from demetra.services.git import git_pull, git_worktree_create
from demetra.services.linear import get_linear_task, get_linear_task_by_id
from demetra.services.tui import print_message


async def setup_workflow(project_name: str, auto_mode: bool, task_id: str | None = None) -> Context | None:
    projects = await search_projects_by_name(name=project_name)
    if not projects:
        print_message(f"Project {project_name} not found", style="error")
        return None

    if len(projects) > 1:
        print_message(f"There are more than one project {project_name} found", style="error")
        return None

    project = Project(**projects[0])
    if not project.local_path:
        print_message(f"No local path found for {project.name} project", style="error")
        return None

    print_message("Loading project environment", style="heading")
    project.environment = await get_project_environments(project_id=project.id, user_id=project.user_id)

    print_message("Retrieving linear task", style="heading")
    if task_id:
        linear_task = await get_linear_task_by_id(task_id)
    else:
        linear_task = await get_linear_task(project_name=project.name)

    if not linear_task:
        print_message(f"No TODO tasks found for {project.name} project", style="error")
        return None

    print_message(f"Retrieved task: {linear_task.full_title}", style="result")

    session = await get_session(task_id=linear_task.id)
    branch_name = linear_task.slug

    print_message("Pulling latest changes", style="heading")
    print_message("")
    await git_pull(target_path=project.local_path, env=project.environment)
    print_message("")

    print_message("Creating feature worktree", style="heading")
    print_message("")
    worktree_path = await git_worktree_create(project=project, branch_name=branch_name, env=project.environment)
    print_message("")
    print_message(f"Created worktree at: {worktree_path}", style="result")

    return Context(
        project=project,
        auto_mode=auto_mode,
        linear_task=linear_task,
        branch_name=branch_name,
        worktree_path=worktree_path,
        session=session,
    )
