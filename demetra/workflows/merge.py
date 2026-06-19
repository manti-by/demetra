import json
import logging
from pathlib import Path

from demetra.library.models import Project
from demetra.services.database import get_project_by_id_system, get_project_environments, get_session
from demetra.services.git import git_add_all, git_fetch, git_force_push, git_worktree_create, git_worktree_remove
from demetra.services.opencode import opencode_merge_agent
from demetra.services.prompt import get_prompt
from demetra.services.subprocess import run_command
from demetra.services.utils import setup_session_logging
from demetra.settings import GIT, GITHUB, MAX_MERGE_ATTEMPTS


logger = logging.getLogger(__name__)


async def run_merge_workflow(task_id: str, project_id: str, pr_number: int, full_name: str) -> bool:
    session = await get_session(task_id)
    if not session:
        logger.error(f"Session not found for task_id: {task_id}")
        return False

    await setup_session_logging(logger=logger, task_id=session.task_id)

    logger.info(f"Starting merge workflow for PR #{pr_number} in {full_name}")

    project_data = await get_project_by_id_system(project_id)
    if not project_data:
        logger.error(f"Project not found for project_id: {project_id}")
        return False

    project = Project(**project_data)
    project.local_path = Path(project.local_path)
    project.environment = await get_project_environments(project_id=project.id, user_id=project.user_id)

    env = project.environment
    worktree_path = None

    try:
        await git_fetch(target_path=project.local_path, env=env)

        pr_cmd = [
            str(GITHUB["path"]),
            "pr",
            "view",
            str(pr_number),
            "--json",
            "headRefName,baseRefName",
            "-R",
            full_name,
        ]
        exit_code, stdout, stderr = await run_command(command=pr_cmd, target_path=project.local_path, env=env)
        if exit_code != 0:
            logger.error(f"Failed to get PR info: {stderr.strip()}")
            return False

        try:
            pr_data = json.loads(stdout)
            head_branch = pr_data["headRefName"]
            base_branch = pr_data["baseRefName"]
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to parse PR info for PR #{pr_number}: {e}")
            return False

        logger.info(f"Merging base '{base_branch}' into '{head_branch}' for PR #{pr_number}")

        worktree_path = await git_worktree_create(
            project=project, branch_name=head_branch, create_branch=False, env=env
        )

        merge_cmd = [str(GIT["path"]), "merge", "-X", "theirs", f"origin/{base_branch}", "--no-edit"]
        exit_code, _, stderr = await run_command(command=merge_cmd, target_path=worktree_path, env=env)
        if exit_code == 0:
            await git_force_push(target_path=worktree_path, branch_name=head_branch, env=env)
            logger.info(f"Successfully merged base into head for PR #{pr_number}")
            return True

        logger.warning(f"Merge with -X theirs failed, attempting conflict resolution: {stderr.strip()[:500]}")

        conflict_cmd = [str(GIT["path"]), "diff", "--name-only", "--diff-filter=U"]
        for attempt in range(MAX_MERGE_ATTEMPTS):
            _, conflict_files, _ = await run_command(
                command=conflict_cmd, target_path=worktree_path, disable_stdio=True, env=env
            )
            conflicted = [f.strip() for f in conflict_files.split("\n") if f.strip()]

            if not conflicted:
                break

            logger.info(f"Conflict resolution attempt {attempt + 1}/{MAX_MERGE_ATTEMPTS}")

            task = await get_prompt(
                "merge_agent",
                conflicted_files="\n".join(f"- {f}" for f in conflicted),
                merge_error=stderr.strip()[:2000],
            )

            agent_exit, agent_out, agent_err = await opencode_merge_agent(
                target_path=worktree_path,
                task=task,
                env=env,
            )

            if agent_exit != 0:
                logger.error(f"Conflict resolution via merge-agent failed: {(agent_err or agent_out).strip()[:500]}")
                return False

        _, remaining, _ = await run_command(
            command=conflict_cmd, target_path=worktree_path, disable_stdio=True, env=env
        )
        if remaining.strip():
            logger.error(f"Conflicts remain after {MAX_MERGE_ATTEMPTS} resolution attempts: {remaining.strip()[:500]}")
            return False

        has_staged = await git_add_all(target_path=worktree_path, env=env)
        if has_staged:
            commit_cmd = [str(GIT["path"]), "commit", "--no-edit"]
            await run_command(command=commit_cmd, target_path=worktree_path, env=env)
        await git_force_push(target_path=worktree_path, branch_name=head_branch, env=env)

        logger.info(f"Successfully merged and resolved conflicts for PR #{pr_number}")
        return True

    except (OSError, RuntimeError) as e:
        logger.error(f"Failed to process merge for PR #{pr_number}: {e}")
        return False
    finally:
        if worktree_path:
            try:
                await git_worktree_remove(
                    target_path=project.local_path, worktree_path=worktree_path, force=True, env=env
                )
            except (OSError, RuntimeError):
                logger.warning(f"Failed to clean up worktree at {worktree_path}")
