import logging
from pathlib import Path

from demetra.services.git import git_add_all, git_force_push
from demetra.services.github import pr_comment
from demetra.services.opencode import opencode_merge_agent
from demetra.services.prompt import get_prompt
from demetra.services.subprocess import run_command
from demetra.settings import GIT, MAX_MERGE_ATTEMPTS


logger = logging.getLogger(__name__)


async def perform_git_merge(
    worktree_path: Path,
    head_branch: str,
    base_branch: str,
    env: dict,
    pr_number: int | None = None,
    full_name: str | None = None,
) -> bool:
    """
    Handles the Git merge process, including conflict resolution with opencode-merge-agent.
    """
    merge_cmd = [str(GIT["path"]), "merge", "-X", "theirs", f"origin/{base_branch}", "--no-edit"]
    exit_code, _, stderr = await run_command(command=merge_cmd, target_path=worktree_path, env=env)

    if exit_code == 0:
        pushed = await git_force_push(target_path=worktree_path, branch_name=head_branch, env=env)
        if not pushed:
            logger.info(f"Nothing to push for branch {head_branch} — already up-to-date")
            if pr_number is not None and full_name is not None:
                comment_body = f"Base branch `{base_branch}` has no new changes to merge into `{head_branch}` — already up-to-date."
                await pr_comment(
                    pr_number=pr_number,
                    full_name=full_name,
                    body=comment_body,
                    target_path=worktree_path,
                    env=env,
                )
        else:
            logger.info(f"Successfully merged base into head for branch {head_branch}")
        return True

    logger.warning(f"Merge with -X theirs failed, attempting conflict resolution: {stderr.strip()[:500]}")

    conflict_cmd = [str(GIT["path"]), "diff", "--name-only", "--diff-filter=U"]
    for attempt in range(MAX_MERGE_ATTEMPTS):
        _, conflict_files, _ = await run_command(
            command=conflict_cmd, target_path=worktree_path, disable_stdio=True, env=env
        )
        conflicted_files = "\n- ".join([f.strip() for f in conflict_files.split("\n") if f.strip()])
        if not conflicted_files:
            break

        logger.info(f"Conflict resolution attempt {attempt + 1}/{MAX_MERGE_ATTEMPTS}")

        task = await get_prompt(
            "merge_agent",
            conflicted_files=conflicted_files,
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

    _, remaining, _ = await run_command(command=conflict_cmd, target_path=worktree_path, disable_stdio=True, env=env)
    if remaining.strip():
        logger.error(f"Conflicts remain after {MAX_MERGE_ATTEMPTS} resolution attempts: {remaining.strip()[:500]}")
        return False

    has_staged = await git_add_all(target_path=worktree_path, env=env)
    if has_staged:
        commit_cmd = [str(GIT["path"]), "commit", "--no-edit"]
        await run_command(command=commit_cmd, target_path=worktree_path, env=env)

    pushed = await git_force_push(target_path=worktree_path, branch_name=head_branch, env=env)
    if not pushed:
        logger.info(f"Nothing to push for branch {head_branch} after conflict resolution — already up-to-date")
    else:
        logger.info(f"Successfully merged and resolved conflicts for branch {head_branch}")
    return True
