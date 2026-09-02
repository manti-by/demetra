import logging
import re
import shutil
from pathlib import Path

from demetra.library.models import Context, Project
from demetra.services.runtime.subprocess import run_command
from demetra.services.runtime.tui import print_message
from demetra.settings import GIT


SAFE_REF_RE = re.compile(r"^[a-zA-Z0-9_\-\.\/]+$")

logger = logging.getLogger(__name__)


def validate_ref(ref: str, label: str) -> None:
    """Validate a git ref name to guard against injection or traversal.

    Rejects refs containing path traversal or other unsafe sequences.

    Args:
        ref: The ref name to validate.
        label: Description of the ref used in error messages.

    Raises:
        RuntimeError: When the ref is empty or unsafe.
    """
    if not ref or not SAFE_REF_RE.fullmatch(ref) or ".." in ref or "@{" in ref:
        raise RuntimeError(f"Invalid {label}: {ref!r}")


def get_worktree_path(project: Project, branch_name: str) -> Path:
    """Compute the filesystem path for a project's branch worktree.

    Args:
        project: The project the worktree belongs to.
        branch_name: The branch the worktree is checked out on.

    Returns:
        Path: The worktree path under the configured worktree directory.
    """
    return GIT["worktree_path"] / project.repository_owner / project.repository_name / branch_name


async def _branch_has_unique_commits(
    target_path: Path, branch_name: str, env: dict[str, str] | None = None, project_id: str | None = None
) -> bool:
    """Return whether a local branch contains commits not on its remote or base.

    Checks ``origin/<branch>..<branch>`` when the remote branch exists,
    otherwise ``origin/master..<branch>``. A non-zero count means the branch
    would lose commits if force-deleted.

    Args:
        target_path: Directory of the main checkout to run git in.
        branch_name: The branch to inspect.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Returns:
        bool: True when the branch has unique commits that would be lost.
    """
    # Check if local branch exists
    verify_cmd = [str(GIT["path"]), "show-ref", "--verify", f"refs/heads/{branch_name}"]
    exit_code, _, _ = await run_command(
        command=verify_cmd, target_path=target_path, disable_stdio=True, env=env, project_id=project_id
    )
    if exit_code != 0:
        return False

    # Prefer origin/<branch> as base when it exists
    remote_branch = f"origin/{branch_name}"
    remote_verify = [str(GIT["path"]), "show-ref", "--verify", f"refs/remotes/{remote_branch}"]
    remote_exit, _, _ = await run_command(
        command=remote_verify, target_path=target_path, disable_stdio=True, env=env, project_id=project_id
    )
    base = remote_branch if remote_exit == 0 else "origin/master"
    # If origin/master also missing, fall back to counting all commits on branch
    count_cmd = [str(GIT["path"]), "rev-list", "--count", f"{base}..{branch_name}"]
    count_exit, stdout, _ = await run_command(
        command=count_cmd, target_path=target_path, disable_stdio=True, env=env, project_id=project_id
    )
    if count_exit != 0:
        # If base doesn't exist, count commits on branch directly
        fallback_cmd = [str(GIT["path"]), "rev-list", "--count", branch_name]
        fallback_exit, fallback_out, _ = await run_command(
            command=fallback_cmd, target_path=target_path, disable_stdio=True, env=env, project_id=project_id
        )
        if fallback_exit == 0:
            try:
                return int(fallback_out.strip()) > 0
            except ValueError:
                return True
        return True
    try:
        return int(stdout.strip()) > 0
    except ValueError:
        return True


async def git_worktree_create(
    project: Project, branch_name: str, env: dict[str, str] | None = None, create_branch: bool = True
) -> Path:
    """Create a git worktree for a branch, cleaning up any stale worktree first.

    When ``create_branch`` is False, the branch is force-created from the
    remote tracking branch before the worktree is added.

    Args:
        project: The project to operate on.
        branch_name: The branch to check out in the worktree.
        env: Optional environment overrides for the subprocess.
        create_branch: Whether to create the branch with the worktree.

    Returns:
        Path: The path of the created worktree.

    Raises:
        RuntimeError: When branch or worktree creation fails.
    """
    worktree_path = get_worktree_path(project=project, branch_name=branch_name)
    if worktree_path.exists():
        git_file = worktree_path / ".git"
        if git_file.exists() and git_file.is_file():
            await git_worktree_remove(
                target_path=project.local_path, worktree_path=worktree_path, force=True, env=env, project_id=project.id
            )
        else:
            shutil.rmtree(worktree_path)
        if await _branch_has_unique_commits(
            target_path=project.local_path, branch_name=branch_name, env=env, project_id=project.id
        ):
            logger.warning(f"Preserving branch {branch_name} with unique commits; skipping force-delete")
        else:
            await git_branch_delete(
                target_path=project.local_path, branch_name=branch_name, env=env, project_id=project.id
            )

    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    if create_branch:
        # If a previous run orphaned the branch (e.g. research success leaves the
        # local branch), the worktree path no longer exists so the stale-branch
        # cleanup above did not run. Ensure the branch does not already exist.
        if not worktree_path.exists():
            if await _branch_has_unique_commits(
                target_path=project.local_path, branch_name=branch_name, env=env, project_id=project.id
            ):
                logger.warning(f"Preserving orphaned branch {branch_name} with unique commits; skipping force-delete")
            else:
                await git_branch_delete(
                    target_path=project.local_path, branch_name=branch_name, env=env, project_id=project.id
                )
        command = [str(GIT["path"]), "worktree", "add", "-b", branch_name, str(worktree_path)]
    else:
        branch_cmd = [str(GIT["path"]), "branch", "--force", branch_name, f"origin/{branch_name}"]
        branch_exit, _, branch_err = await run_command(
            command=branch_cmd, target_path=project.local_path, env=env, project_id=project.id
        )
        if branch_exit != 0:
            raise RuntimeError(f"Failed to create branch {branch_name}: {branch_err.strip() or 'unknown error'}")
        command = [str(GIT["path"]), "worktree", "add", str(worktree_path), branch_name]

    exit_code, _, stderr = await run_command(
        command=command, target_path=project.local_path, env=env, project_id=project.id
    )
    if exit_code != 0:
        raise RuntimeError(f"Failed to create worktree at {worktree_path}: {stderr.strip() or 'unknown error'}")

    return worktree_path


async def git_worktree_remove(
    target_path: Path,
    worktree_path: Path,
    force: bool = False,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
) -> None:
    """Remove a git worktree, optionally forcing removal.

    Args:
        target_path: Directory of the main checkout to run git in.
        worktree_path: Path of the worktree to remove.
        force: Whether to pass ``--force`` to git.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Raises:
        RuntimeError: When the worktree removal fails.
    """
    command = [str(GIT["path"]), "worktree", "remove", str(worktree_path)]
    if force:
        command.append("--force")
    exit_code, _, stderr = await run_command(command=command, target_path=target_path, env=env, project_id=project_id)
    if exit_code != 0:
        raise RuntimeError(f"Failed to remove worktree {worktree_path}: {stderr.strip() or 'unknown error'}")


async def git_add_all(target_path: Path, env: dict[str, str] | None = None, project_id: str | None = None) -> bool:
    """Stage all changes in a directory and report whether anything was staged.

    Args:
        target_path: Directory of the git repository.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Returns:
        bool: True when at least one file was staged.
    """
    command = [str(GIT["path"]), "add", "."]
    await run_command(command=command, target_path=target_path, env=env, project_id=project_id)

    diff_cmd = [str(GIT["path"]), "diff", "--staged", "--name-only"]
    _, stdout, _ = await run_command(
        command=diff_cmd, target_path=target_path, disable_stdio=True, env=env, project_id=project_id
    )
    return bool(stdout.strip())


async def git_commit(
    target_path: Path, message: str, env: dict[str, str] | None = None, project_id: str | None = None
) -> None:
    """Commit the staged changes with the given message.

    Args:
        target_path: Directory of the git repository.
        message: The commit message.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Raises:
        RuntimeError: When the commit fails.
    """
    command = [str(GIT["path"]), "commit", "-m", message]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=target_path, env=env, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(f"Commit failed: {stderr.strip() or stdout.strip() or 'unknown error'}")


async def git_pull(
    target_path: Path,
    branch_name: str = "master",
    env: dict[str, str] | None = None,
    project_id: str | None = None,
) -> None:
    """Pull updates for a branch from the origin remote.

    Args:
        target_path: Directory of the git repository.
        branch_name: The remote branch to pull, defaulting to ``"master"``.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
    """
    command = [str(GIT["path"]), "pull", "origin", branch_name]
    await run_command(command=command, target_path=target_path, env=env, project_id=project_id)


async def git_push(
    target_path: Path, branch_name: str, env: dict[str, str] | None = None, project_id: str | None = None
) -> None:
    """Push a branch to origin, setting its upstream tracking.

    Args:
        target_path: Directory of the git repository.
        branch_name: The branch to push.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Raises:
        RuntimeError: When the push fails.
    """
    command = [str(GIT["path"]), "push", "--set-upstream", "origin", branch_name]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=target_path, env=env, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(f"Push failed: {stderr.strip() or stdout.strip() or 'unknown error'}")


async def git_branch_delete(
    target_path: Path, branch_name: str, env: dict[str, str] | None = None, project_id: str | None = None
) -> None:
    """Force-delete a local branch.

    Args:
        target_path: Directory of the git repository.
        branch_name: The branch to delete.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
    """
    command = [str(GIT["path"]), "branch", "-D", branch_name]
    await run_command(command=command, target_path=target_path, env=env, project_id=project_id)


async def git_fetch(target_path: Path, env: dict[str, str] | None = None, project_id: str | None = None) -> None:
    """Fetch updates from all configured remotes.

    Args:
        target_path: Directory of the git repository.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Raises:
        RuntimeError: When the fetch fails.
    """
    command = [str(GIT["path"]), "fetch", "--all"]
    exit_code, _, stderr = await run_command(command=command, target_path=target_path, env=env, project_id=project_id)
    if exit_code != 0:
        raise RuntimeError(f"Fetch failed: {stderr.strip()}")


async def git_checkout(
    target_path: Path, branch_name: str, env: dict[str, str] | None = None, project_id: str | None = None
) -> None:
    """Check out a branch in a repository.

    Args:
        target_path: Directory of the git repository.
        branch_name: The branch to check out.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
    """
    command = [str(GIT["path"]), "checkout", branch_name]
    await run_command(command=command, target_path=target_path, env=env, project_id=project_id)


async def git_rebase(
    target_path: Path, base_branch: str, env: dict[str, str] | None = None, project_id: str | None = None
) -> bool:
    """Rebase the current branch onto a remote base branch, preferring theirs.

    Args:
        target_path: Directory of the git repository.
        base_branch: The remote base branch to rebase onto.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Returns:
        bool: True when the rebase succeeded.

    Raises:
        RuntimeError: When the rebase fails.
    """
    command = [str(GIT["path"]), "rebase", "-X", "theirs", f"origin/{base_branch}"]
    exit_code, _, stderr = await run_command(command=command, target_path=target_path, env=env, project_id=project_id)
    if exit_code == 0:
        return True
    raise RuntimeError(f"Rebase failed: {stderr.strip()}")


async def git_has_unpushed_commits(
    target_path: Path, branch_name: str, env: dict[str, str] | None = None, project_id: str | None = None
) -> bool:
    """Return whether the branch has local commits not on the remote.

    Args:
        target_path: Directory of the git repository.
        branch_name: The branch to compare against its remote tracking branch.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Returns:
        bool: True when there are unpushed commits.

    Raises:
        RuntimeError: When the git command fails or its output is malformed.
    """
    cmd = [str(GIT["path"]), "rev-list", "--count", f"origin/{branch_name}..HEAD"]
    exit_code, stdout, stderr = await run_command(
        command=cmd, target_path=target_path, disable_stdio=True, env=env, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(f"Failed to check unpushed commits for {branch_name}: {stderr.strip() or 'unknown error'}")
    try:
        return int(stdout.strip()) > 0
    except ValueError as e:
        raise RuntimeError(f"Malformed rev-list output for {branch_name}: {stdout.strip()!r}") from e


async def git_force_push(
    target_path: Path, branch_name: str, env: dict[str, str] | None = None, project_id: str | None = None
) -> bool:
    """Force-push a branch with lease protection.

    Args:
        target_path: Directory of the git repository.
        branch_name: The branch to push.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Returns:
        bool: True when commits were actually pushed, False when the branch
            was already up to date.

    Raises:
        RuntimeError: When the force push fails.
    """
    command = [str(GIT["path"]), "push", "--force-with-lease", "origin", branch_name]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=target_path, env=env, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(f"Force push failed: {stderr.strip()}")
    # If push reports "Everything up-to-date", nothing was actually pushed
    if "Everything up-to-date" in stdout or "Everything up-to-date" in stderr:
        return False
    return True


async def git_cleanup(context: Context, is_success: bool):
    """Clean up a workflow's worktree and branch after a run finishes.

    Always removes the worktree, forcing it on failure. On failure the branch
    is also force-deleted.

    Args:
        context: The workflow context describing the worktree and branch.
        is_success: Whether the workflow completed successfully.
    """
    env = context.project.environment
    project_id = context.project.id
    try:
        print_message("Removing worktree", style="heading")
        await git_worktree_remove(
            target_path=context.project.local_path,
            worktree_path=context.worktree_path,
            force=(not is_success),
            env=env,
            project_id=project_id,
        )
    except (OSError, RuntimeError, AttributeError):
        print_message("Failed to remove worktree", style="error")

    if is_success:
        return

    try:
        print_message("Deleting branch", style="heading")
        await git_branch_delete(
            target_path=context.project.local_path, branch_name=context.branch_name, env=env, project_id=project_id
        )
    except (OSError, RuntimeError, AttributeError):
        print_message("Failed to delete branch", style="error")
