from demetra.library.models import Chat, Context, Project, SessionEnvironment
from demetra.services.auth.copy import copy_auth_from_parent
from demetra.services.chat import get_chat_task
from demetra.services.linear import get_linear_task, get_linear_task_by_id
from demetra.services.persistence.database import (
    get_project_environments,
    get_session,
    get_user_environments_decrypted,
    search_projects_by_name,
)
from demetra.services.runtime.project import setup_project_venv
from demetra.services.runtime.tui import print_message
from demetra.services.vcs.git import (
    get_worktree_path,
    git_pull,
    git_worktree_create,
    git_worktree_drop,
    git_worktree_exists,
    git_worktree_has_operation,
)
from demetra.settings import FEATURES, PARENT_HOME
from demetra.workflows.research import is_research_task


async def setup_workflow(project_name: str, auto_mode: bool, task_id: str | None = None) -> Context | None:
    """Prepare a project and task into a runnable workflow context.

    Loads the project, its environment, the owner's user-shared environment,
    auth, and the per-project UV venv, then resolves the task (from a task id
    or the next TODO). An existing worktree is reused as-is unless it has an
    unfinished git operation or ``WORKTREE_CLEANUP`` is enabled; in those cases
    the worktree and its branch are dropped, latest master is pulled and a
    fresh worktree is created. Research tasks skip the branch and worktree, run
    read-only in the main checkout and always pull master.

    Args:
        project_name: The name of the project to run.
        auto_mode: Whether the workflow runs without user interaction.
        task_id: Optional Linear task id; otherwise the next TODO is picked.

    Returns:
        Context | None: The prepared context, or None when setup fails.
    """
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

    if project.user_id:
        print_message("Loading user-shared environment", style="heading")
        project.user_environment = await get_user_environments_decrypted(user_id=project.user_id)

    print_message("Setting up project UV venv", style="heading")
    await setup_project_venv(project=project)

    environment = SessionEnvironment(project_environment=project.environment, user_environment=project.user_environment)

    print_message("Copying auth from parent OS", style="heading")
    await copy_auth_from_parent(parent_home=PARENT_HOME)

    print_message("Retrieving task", style="heading")
    chat: Chat | None = None
    if task_id:
        if (chat_task := await get_chat_task(task_id=task_id)) is not None:
            task, chat = chat_task
        else:
            task = await get_linear_task_by_id(task_id=task_id)
    else:
        task = await get_linear_task(project_name=project.name, user_id=project.user_id)

    if not task:
        print_message(f"No TODO tasks found for {project.name} project", style="error")
        return None

    print_message(f"Retrieved task: {task.full_title}", style="result")

    session = await get_session(task_id=task.id)
    branch_name = task.slug
    worktree_path = get_worktree_path(project=project, branch_name=branch_name)
    recreate = FEATURES["is_worktree_cleanup_enabled"]

    if is_research_task(task=task):
        # Research is read-only: it needs no branch or worktree and runs in
        # the main checkout. It still needs the latest master for the agent.
        print_message("Pulling latest changes", style="heading")
        print_message("")
        await git_pull(target_path=project.local_path, environment=environment, project_id=project.id)
        print_message("")
        print_message("Research task: skipping branch and worktree creation", style="heading")
        return Context(
            project=project,
            auto_mode=auto_mode,
            task=task,
            branch_name=branch_name,
            worktree_path=project.local_path,
            session=session,
            is_research=True,
            chat=chat,
        )

    if recreate:
        print_message("Dropping existing worktree", style="heading")
        await git_worktree_drop(project=project, branch_name=branch_name, environment=environment)
        needs_worktree = True
    else:
        needs_worktree = not git_worktree_exists(project=project, branch_name=branch_name)
        if not needs_worktree and await git_worktree_has_operation(
            project=project, branch_name=branch_name, environment=environment
        ):
            print_message("Existing worktree has an unfinished git operation, recreating it", style="warning")
            needs_worktree = True

    if needs_worktree:
        print_message("Pulling latest changes", style="heading")
        print_message("")
        await git_pull(target_path=project.local_path, environment=environment, project_id=project.id)
        print_message("")

        print_message("Creating feature worktree", style="heading")
        print_message("")
        worktree_path = await git_worktree_create(project=project, branch_name=branch_name, environment=environment)
        print_message("")
        print_message(f"Created worktree at: {worktree_path}", style="result")
    else:
        print_message(f"Reusing existing worktree at: {worktree_path}", style="result")

    return Context(
        project=project,
        auto_mode=auto_mode,
        task=task,
        branch_name=branch_name,
        worktree_path=worktree_path,
        session=session,
        chat=chat,
    )
