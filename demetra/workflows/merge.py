import logging
from pathlib import Path

from demetra.library.models import Context, Project
from demetra.services.linear import get_linear_task_by_id
from demetra.services.persistence.database import (
    get_project_by_id_system,
    get_project_environments,
    get_session,
    get_user_environments_decrypted,
)
from demetra.services.persistence.queue import queue
from demetra.services.runtime.project import setup_project_venv
from demetra.services.runtime.utils import setup_session_logging
from demetra.services.vcs.git import git_fetch, git_worktree_create, git_worktree_remove, validate_ref
from demetra.services.vcs.github import get_pr_info
from demetra.services.vcs.merge import perform_git_merge
from demetra.services.wiki import run_wiki_revalidation, write_session_wiki_page
from demetra.settings import WIKI_REVALIDATION_ENABLED


logger = logging.getLogger(__name__)


async def run_merge_workflow(task_id: str, project_id: str, pr_number: int, full_name: str) -> bool:
    """Merge a pull request and resolve conflicts via the merge agent.

    Loads the session and project, creates a worktree for the PR head branch,
    performs the merge and cleans up the worktree afterwards.

    Args:
        task_id: The Linear task identifier.
        project_id: The project id the PR belongs to.
        pr_number: The pull request number.
        full_name: The repository full name, e.g. ``"owner/repo"``.

    Returns:
        bool: True when the merge succeeded.
    """
    session = await get_session(task_id=task_id)
    if not session:
        logger.error(f"Session not found for task_id: {task_id}")
        return False

    await setup_session_logging(task_id=session.task_id)

    logger.info(f"Starting merge workflow for PR #{pr_number} in {full_name}")

    project_data = await get_project_by_id_system(project_id=project_id)
    if not project_data:
        logger.error(f"Project not found for project_id: {project_id}")
        return False

    project = Project(**project_data)
    project.local_path = Path(project.local_path)
    project.environment = await get_project_environments(project_id=project.id, user_id=project.user_id)
    if project.user_id:
        project.user_environment = await get_user_environments_decrypted(user_id=project.user_id)
        project.environment = {**project.user_environment, **project.environment}
    await setup_project_venv(project=project)

    worktree_path = None
    merge_succeeded = False
    try:
        pr_info = await get_pr_info(
            pr_number=pr_number,
            full_name=full_name,
            target_path=project.local_path,
            env=project.environment,
            project_id=project.id,
        )
        if not pr_info:
            return False

        head_branch, base_branch = pr_info

        await git_fetch(target_path=project.local_path, env=project.environment, project_id=project.id)

        validate_ref(head_branch, "head branch")
        validate_ref(base_branch, "base branch")

        worktree_path = await git_worktree_create(
            project=project, branch_name=head_branch, env=project.environment, create_branch=False
        )

        merge_succeeded = await perform_git_merge(
            worktree_path=worktree_path,
            head_branch=head_branch,
            base_branch=base_branch,
            env=project.environment,
            pr_number=pr_number,
            full_name=full_name,
            project_id=project.id,
        )
        if merge_succeeded:
            logger.info(f"Successfully merged and resolved conflicts for PR #{pr_number}")
            return True

    except (OSError, RuntimeError) as e:
        logger.error(f"Failed to process merge for PR #{pr_number}: {e}")
        return False

    finally:
        if worktree_path and merge_succeeded:
            try:
                linear_task = await get_linear_task_by_id(task_id=task_id)
                if linear_task is not None:
                    context = Context(
                        project=project,
                        auto_mode=True,
                        linear_task=linear_task,
                        branch_name=head_branch,
                        worktree_path=worktree_path,
                        session=session,
                    )
                    await write_session_wiki_page(context=context)
            except Exception:  # noqa: BLE001
                logger.warning(msg="Failed to write wiki page for merge session, continuing")
            if WIKI_REVALIDATION_ENABLED:
                try:
                    queue.enqueue(f=run_wiki_revalidation)
                except Exception:  # noqa: BLE001
                    logger.warning(msg="Failed to enqueue wiki revalidation, merge result unaffected")
        if worktree_path:
            try:
                await git_worktree_remove(
                    target_path=project.local_path,
                    worktree_path=worktree_path,
                    env=project.environment,
                    force=True,
                    project_id=project.id,
                )
            except (OSError, RuntimeError):
                logger.warning(msg=f"Failed to clean up worktree at {worktree_path}")

    return False
