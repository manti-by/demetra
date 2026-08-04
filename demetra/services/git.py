import logging
import re
import shutil
from pathlib import Path

from demetra.library.models import Context, Project
from demetra.services.subprocess import run_command
from demetra.services.tui import print_message
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
            await git_worktree_remove(target_path=project.local_path, worktree_path=worktree_path, force=True, env=env)
        else:
            shutil.rmtree(worktree_path)
        await git_branch_delete(target_path=project.local_path, branch_name=branch_name, env=env)

    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    if create_branch:
        command = [str(GIT["path"]), "worktree", "add", "-b", branch_name, str(worktree_path)]
    else:
        branch_cmd = [str(GIT["path"]), "branch", "--force", branch_name, f"origin/{branch_name}"]
        branch_exit, _, branch_err = await run_command(command=branch_cmd, target_path=project.local_path, env=env)
        if branch_exit != 0:
            raise RuntimeError(f"Failed to create branch {branch_name}: {branch_err.strip() or 'unknown error'}")
        command = [str(GIT["path"]), "worktree", "add", str(worktree_path), branch_name]

    exit_code, _, stderr = await run_command(command=command, target_path=project.local_path, env=env)
    if exit_code != 0:
        raise RuntimeError(f"Failed to create worktree at {worktree_path}: {stderr.strip() or 'unknown error'}")

    return worktree_path


async def git_worktree_remove(
    target_path: Path, worktree_path: Path, force: bool = False, env: dict[str, str] | None = None
):
    """Remove a git worktree, optionally forcing removal.

    Args:
        target_path: Directory of the main checkout to run git in.
        worktree_path: Path of the worktree to remove.
        force: Whether to pass ``--force`` to git.
        env: Optional environment overrides for the subprocess.

    Raises:
        RuntimeError: When the worktree removal fails.
    """
    command = [str(GIT["path"]), "worktree", "remove", str(worktree_path)]
    if force:
        command.append("--force")
    exit_code, _, stderr = await run_command(command=command, target_path=target_path, env=env)
    if exit_code != 0:
        raise RuntimeError(f"Failed to remove worktree {worktree_path}: {stderr.strip() or 'unknown error'}")


async def git_add_all(target_path: Path, env: dict[str, str] | None = None) -> bool:
    """Stage all changes in a directory and report whether anything was staged.

    Args:
        target_path: Directory of the git repository.
        env: Optional environment overrides for the subprocess.

    Returns:
        bool: True when at least one file was staged.
    """
    command = [str(GIT["path"]), "add", "."]
    await run_command(command=command, target_path=target_path, env=env)

    diff_cmd = [str(GIT["path"]), "diff", "--staged", "--name-only"]
    _, stdout, _ = await run_command(command=diff_cmd, target_path=target_path, disable_stdio=True, env=env)
    return bool(stdout.strip())


async def git_commit(target_path: Path, message: str, env: dict[str, str] | None = None):
    """Commit the staged changes with the given message.

    Args:
        target_path: Directory of the git repository.
        message: The commit message.
        env: Optional environment overrides for the subprocess.

    Raises:
        RuntimeError: When the commit fails.
    """
    command = [str(GIT["path"]), "commit", "-m", message]
    exit_code, stdout, stderr = await run_command(command=command, target_path=target_path, env=env)
    if exit_code != 0:
        raise RuntimeError(f"Commit failed: {stderr.strip() or stdout.strip() or 'unknown error'}")


async def git_pull(target_path: Path, branch_name: str = "master", env: dict[str, str] | None = None):
    """Pull updates for a branch from the origin remote.

    Args:
        target_path: Directory of the git repository.
        branch_name: The remote branch to pull, defaulting to ``"master"``.
        env: Optional environment overrides for the subprocess.
    """
    command = [str(GIT["path"]), "pull", "origin", branch_name]
    await run_command(command=command, target_path=target_path, env=env)


async def git_push(target_path: Path, branch_name: str, env: dict[str, str] | None = None):
    """Push a branch to origin, setting its upstream tracking.

    Args:
        target_path: Directory of the git repository.
        branch_name: The branch to push.
        env: Optional environment overrides for the subprocess.

    Raises:
        RuntimeError: When the push fails.
    """
    command = [str(GIT["path"]), "push", "--set-upstream", "origin", branch_name]
    exit_code, stdout, stderr = await run_command(command=command, target_path=target_path, env=env)
    if exit_code != 0:
        raise RuntimeError(f"Push failed: {stderr.strip() or stdout.strip() or 'unknown error'}")


async def git_branch_delete(target_path: Path, branch_name: str, env: dict[str, str] | None = None):
    """Force-delete a local branch.

    Args:
        target_path: Directory of the git repository.
        branch_name: The branch to delete.
        env: Optional environment overrides for the subprocess.
    """
    command = [str(GIT["path"]), "branch", "-D", branch_name]
    await run_command(command=command, target_path=target_path, env=env)


async def git_fetch(target_path: Path, env: dict[str, str] | None = None):
    """Fetch updates from all configured remotes.

    Args:
        target_path: Directory of the git repository.
        env: Optional environment overrides for the subprocess.

    Raises:
        RuntimeError: When the fetch fails.
    """
    command = [str(GIT["path"]), "fetch", "--all"]
    exit_code, _, stderr = await run_command(command=command, target_path=target_path, env=env)
    if exit_code != 0:
        raise RuntimeError(f"Fetch failed: {stderr.strip()}")


async def git_checkout(target_path: Path, branch_name: str, env: dict[str, str] | None = None):
    """Check out a branch in a repository.

    Args:
        target_path: Directory of the git repository.
        branch_name: The branch to check out.
        env: Optional environment overrides for the subprocess.
    """
    command = [str(GIT["path"]), "checkout", branch_name]
    await run_command(command=command, target_path=target_path, env=env)


async def git_rebase(target_path: Path, base_branch: str, env: dict[str, str] | None = None) -> bool:
    """Rebase the current branch onto a remote base branch, preferring theirs.

    Args:
        target_path: Directory of the git repository.
        base_branch: The remote base branch to rebase onto.
        env: Optional environment overrides for the subprocess.

    Returns:
        bool: True when the rebase succeeded.

    Raises:
        RuntimeError: When the rebase fails.
    """
    command = [str(GIT["path"]), "rebase", "-X", "theirs", f"origin/{base_branch}"]
    exit_code, _, stderr = await run_command(command=command, target_path=target_path, env=env)
    if exit_code == 0:
        return True
    raise RuntimeError(f"Rebase failed: {stderr.strip()}")


async def git_force_push(target_path: Path, branch_name: str, env: dict[str, str] | None = None) -> bool:
    """Force-push a branch with lease protection.

    Args:
        target_path: Directory of the git repository.
        branch_name: The branch to push.
        env: Optional environment overrides for the subprocess.

    Returns:
        bool: True when commits were actually pushed, False when the branch
            was already up to date.

    Raises:
        RuntimeError: When the force push fails.
    """
    command = [str(GIT["path"]), "push", "--force-with-lease", "origin", branch_name]
    exit_code, stdout, stderr = await run_command(command=command, target_path=target_path, env=env)
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
    try:
        print_message("Removing worktree", style="heading")
        await git_worktree_remove(
            target_path=context.project.local_path, worktree_path=context.worktree_path, force=(not is_success), env=env
        )
    except (OSError, RuntimeError, AttributeError):
        print_message("Failed to remove worktree", style="error")

    if is_success:
        return

    try:
        print_message("Deleting branch", style="heading")
        await git_branch_delete(target_path=context.project.local_path, branch_name=context.branch_name, env=env)
    except (OSError, RuntimeError, AttributeError):
        print_message("Failed to delete branch", style="error")
