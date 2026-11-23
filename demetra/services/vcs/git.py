import re
import shutil
from pathlib import Path

from demetra.library.models import Context, Project, SessionEnvironment
from demetra.services.runtime.subprocess import run_command
from demetra.services.runtime.tui import print_message
from demetra.settings import GIT


SAFE_REF_RE = re.compile(r"^[a-zA-Z0-9_\-\.\/]+$")

GIT_OPERATION_MARKERS = (
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "REBASE_HEAD",
    "rebase-merge",
    "rebase-apply",
)


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


def git_worktree_exists(project: Project, branch_name: str) -> bool:
    """Return whether a live worktree for the branch is already on disk.

    Args:
        project: The project the worktree belongs to.
        branch_name: The branch the worktree is checked out on.

    Returns:
        bool: True when the worktree directory exists and carries a .git marker.
    """
    worktree_path = get_worktree_path(project=project, branch_name=branch_name)
    return worktree_path.exists() and (worktree_path / ".git").exists()


async def git_worktree_has_operation(
    project: Project, branch_name: str, environment: SessionEnvironment | None = None
) -> bool:
    """Return whether a worktree has an unfinished git operation.

    A failed merge or rebase workflow leaves ``MERGE_HEAD`` or rebase state in
    its worktree when its own forced cleanup fails. Such a worktree cannot be
    reused: the next run would start inside the unresolved operation. A
    worktree whose git directory cannot be resolved is unsafe for the same
    reason.

    Args:
        project: The project the worktree belongs to.
        branch_name: The branch checked out in the worktree.
        environment: The resolved session environment forwarded to the subprocess.

    Returns:
        bool: True when the worktree must not be reused as-is.
    """
    worktree_path = get_worktree_path(project=project, branch_name=branch_name)
    if not worktree_path.exists():
        return False
    try:
        exit_code, stdout, _ = await run_command(
            command=[str(GIT["path"]), "rev-parse", "--absolute-git-dir"],
            target_path=worktree_path,
            disable_stdio=True,
            environment=environment,
            project_id=project.id,
        )
    except OSError:
        return True
    if exit_code != 0 or not stdout.strip():
        return True
    git_dir = Path(stdout.strip())
    return any((git_dir / marker).exists() for marker in GIT_OPERATION_MARKERS)


async def git_branch_exists(
    target_path: Path, branch_name: str, environment: SessionEnvironment | None = None, project_id: str | None = None
) -> bool:
    """Return whether a local branch exists.

    Args:
        target_path: Directory of the main checkout to run git in.
        branch_name: The branch to look up.
        environment: The resolved session environment forwarded to the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Returns:
        bool: True when the branch exists.
    """
    command = [str(GIT["path"]), "show-ref", "--verify", f"refs/heads/{branch_name}"]
    exit_code, _, _ = await run_command(
        command=command, target_path=target_path, disable_stdio=True, environment=environment, project_id=project_id
    )
    return exit_code == 0


async def git_worktree_create(
    project: Project,
    branch_name: str,
    environment: SessionEnvironment | None = None,
    create_branch: bool = True,
) -> Path:
    """Create a git worktree for a branch, replacing any existing worktree.

    When ``create_branch`` is False, the branch is force-created from the
    remote tracking branch before the worktree is added. Otherwise any local
    branch left over from a previous run is force-deleted first, so the
    worktree always starts from the current checkout.

    Args:
        project: The project to operate on.
        branch_name: The branch to check out in the worktree.
        environment: The resolved session environment forwarded to the subprocess.
        create_branch: Whether to create the branch with the worktree.

    Returns:
        Path: The path of the created worktree.

    Raises:
        RuntimeError: When branch or worktree creation fails.
    """
    worktree_path = get_worktree_path(project=project, branch_name=branch_name)
    if worktree_path.exists():
        await git_worktree_drop(project=project, branch_name=branch_name, environment=environment)

    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    if create_branch:
        if await git_branch_exists(target_path=project.local_path, branch_name=branch_name, environment=environment):
            await git_branch_delete(
                target_path=project.local_path, branch_name=branch_name, environment=environment, project_id=project.id
            )
        command = [str(GIT["path"]), "worktree", "add", "-b", branch_name, str(worktree_path)]
    else:
        branch_cmd = [str(GIT["path"]), "branch", "--force", branch_name, f"origin/{branch_name}"]
        branch_exit, _, branch_err = await run_command(
            command=branch_cmd, target_path=project.local_path, environment=environment, project_id=project.id
        )
        if branch_exit != 0:
            raise RuntimeError(f"Failed to create branch {branch_name}: {branch_err.strip() or 'unknown error'}")
        command = [str(GIT["path"]), "worktree", "add", str(worktree_path), branch_name]

    exit_code, _, stderr = await run_command(
        command=command, target_path=project.local_path, environment=environment, project_id=project.id
    )
    if exit_code != 0:
        raise RuntimeError(f"Failed to create worktree at {worktree_path}: {stderr.strip() or 'unknown error'}")

    return worktree_path


async def git_worktree_remove(
    target_path: Path,
    worktree_path: Path,
    force: bool = False,
    environment: SessionEnvironment | None = None,
    project_id: str | None = None,
) -> None:
    """Remove a git worktree, optionally forcing removal.

    Args:
        target_path: Directory of the main checkout to run git in.
        worktree_path: Path of the worktree to remove.
        force: Whether to pass ``--force`` to git.
        environment: The resolved session environment forwarded to the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Raises:
        RuntimeError: When the worktree removal fails.
    """
    command = [str(GIT["path"]), "worktree", "remove", str(worktree_path)]
    if force:
        command.append("--force")
    exit_code, _, stderr = await run_command(
        command=command, target_path=target_path, environment=environment, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(f"Failed to remove worktree {worktree_path}: {stderr.strip() or 'unknown error'}")


async def git_worktree_drop(project: Project, branch_name: str, environment: SessionEnvironment | None = None) -> None:
    """Force-remove a worktree and its local branch, tolerating stale paths.

    Args:
        project: The project to operate on.
        branch_name: The branch checked out in the worktree.
        environment: The resolved session environment forwarded to the subprocess.
    """
    worktree_path = get_worktree_path(project=project, branch_name=branch_name)
    if worktree_path.exists():
        if (worktree_path / ".git").is_file():
            await git_worktree_remove(
                target_path=project.local_path,
                worktree_path=worktree_path,
                force=True,
                environment=environment,
                project_id=project.id,
            )
        else:
            shutil.rmtree(worktree_path)
    if await git_branch_exists(
        target_path=project.local_path, branch_name=branch_name, environment=environment, project_id=project.id
    ):
        await git_branch_delete(
            target_path=project.local_path, branch_name=branch_name, environment=environment, project_id=project.id
        )


async def git_add_all(
    target_path: Path, environment: SessionEnvironment | None = None, project_id: str | None = None
) -> bool:
    """Stage all changes in a directory and report whether anything was staged.

    Args:
        target_path: Directory of the git repository.
        environment: The resolved session environment forwarded to the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Returns:
        bool: True when at least one file was staged.

    Raises:
        RuntimeError: When staging or inspecting the staged changes fails.
    """
    command = [str(GIT["path"]), "add", "."]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=target_path, environment=environment, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(f"Failed to stage changes: {stderr.strip() or stdout.strip() or 'unknown error'}")

    diff_cmd = [str(GIT["path"]), "diff", "--staged", "--name-only"]
    exit_code, stdout, stderr = await run_command(
        command=diff_cmd, target_path=target_path, disable_stdio=True, environment=environment, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(f"Failed to inspect staged changes: {stderr.strip() or stdout.strip() or 'unknown error'}")
    return bool(stdout.strip())


async def git_commit(
    target_path: Path, message: str, environment: SessionEnvironment | None = None, project_id: str | None = None
) -> None:
    """Commit the staged changes with the given message.

    Args:
        target_path: Directory of the git repository.
        message: The commit message.
        environment: The resolved session environment forwarded to the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Raises:
        RuntimeError: When the commit fails.
    """
    command = [str(GIT["path"]), "commit", "-m", message]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=target_path, environment=environment, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(f"Commit failed: {stderr.strip() or stdout.strip() or 'unknown error'}")


async def git_pull(
    target_path: Path,
    branch_name: str = "master",
    environment: SessionEnvironment | None = None,
    project_id: str | None = None,
) -> None:
    """Pull updates for a branch from the origin remote.

    Args:
        target_path: Directory of the git repository.
        branch_name: The remote branch to pull, defaulting to ``"master"``.
        environment: The resolved session environment forwarded to the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Raises:
        RuntimeError: When the pull fails.
    """
    command = [str(GIT["path"]), "pull", "origin", branch_name]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=target_path, environment=environment, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(f"Pull failed: {stderr.strip() or stdout.strip() or 'unknown error'}")


async def git_push(
    target_path: Path, branch_name: str, environment: SessionEnvironment | None = None, project_id: str | None = None
) -> None:
    """Push a branch to origin, setting its upstream tracking.

    Args:
        target_path: Directory of the git repository.
        branch_name: The branch to push.
        environment: The resolved session environment forwarded to the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Raises:
        RuntimeError: When the push fails.
    """
    command = [str(GIT["path"]), "push", "--set-upstream", "origin", branch_name]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=target_path, environment=environment, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(f"Push failed: {stderr.strip() or stdout.strip() or 'unknown error'}")


async def git_branch_delete(
    target_path: Path, branch_name: str, environment: SessionEnvironment | None = None, project_id: str | None = None
) -> None:
    """Force-delete a local branch.

    Args:
        target_path: Directory of the git repository.
        branch_name: The branch to delete.
        environment: The resolved session environment forwarded to the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Raises:
        RuntimeError: When the branch deletion fails.
    """
    command = [str(GIT["path"]), "branch", "-D", branch_name]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=target_path, environment=environment, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(
            f"Failed to delete branch {branch_name}: {stderr.strip() or stdout.strip() or 'unknown error'}"
        )


async def git_fetch(
    target_path: Path, environment: SessionEnvironment | None = None, project_id: str | None = None
) -> None:
    """Fetch updates from all configured remotes.

    Args:
        target_path: Directory of the git repository.
        environment: The resolved session environment forwarded to the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Raises:
        RuntimeError: When the fetch fails.
    """
    command = [str(GIT["path"]), "fetch", "--all"]
    exit_code, _, stderr = await run_command(
        command=command, target_path=target_path, environment=environment, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(f"Fetch failed: {stderr.strip()}")


async def git_checkout(
    target_path: Path, branch_name: str, environment: SessionEnvironment | None = None, project_id: str | None = None
) -> None:
    """Check out a branch in a repository.

    Args:
        target_path: Directory of the git repository.
        branch_name: The branch to check out.
        environment: The resolved session environment forwarded to the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Raises:
        RuntimeError: When the checkout fails.
    """
    command = [str(GIT["path"]), "checkout", branch_name]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=target_path, environment=environment, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(f"Checkout failed: {stderr.strip() or stdout.strip() or 'unknown error'}")


async def git_rebase(
    target_path: Path, base_branch: str, environment: SessionEnvironment | None = None, project_id: str | None = None
) -> bool:
    """Rebase the current branch onto a remote base branch, preferring theirs.

    Args:
        target_path: Directory of the git repository.
        base_branch: The remote base branch to rebase onto.
        environment: The resolved session environment forwarded to the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Returns:
        bool: True when the rebase succeeded.

    Raises:
        RuntimeError: When the rebase fails.
    """
    command = [str(GIT["path"]), "rebase", "-X", "theirs", f"origin/{base_branch}"]
    exit_code, _, stderr = await run_command(
        command=command, target_path=target_path, environment=environment, project_id=project_id
    )
    if exit_code == 0:
        return True
    raise RuntimeError(f"Rebase failed: {stderr.strip()}")


async def git_has_unpushed_commits(
    target_path: Path, branch_name: str, environment: SessionEnvironment | None = None, project_id: str | None = None
) -> bool:
    """Return whether the branch has local commits not on the remote.

    Args:
        target_path: Directory of the git repository.
        branch_name: The branch to compare against its remote tracking branch.
        environment: The resolved session environment forwarded to the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Returns:
        bool: True when there are unpushed commits.

    Raises:
        RuntimeError: When the git command fails or its output is malformed.
    """
    cmd = [str(GIT["path"]), "rev-list", "--count", f"origin/{branch_name}..HEAD"]
    exit_code, stdout, stderr = await run_command(
        command=cmd, target_path=target_path, disable_stdio=True, environment=environment, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(f"Failed to check unpushed commits for {branch_name}: {stderr.strip() or 'unknown error'}")
    try:
        return int(stdout.strip()) > 0
    except ValueError as e:
        raise RuntimeError(f"Malformed rev-list output for {branch_name}: {stdout.strip()!r}") from e


async def git_force_push(
    target_path: Path, branch_name: str, environment: SessionEnvironment | None = None, project_id: str | None = None
) -> bool:
    """Force-push a branch with lease protection.

    Args:
        target_path: Directory of the git repository.
        branch_name: The branch to push.
        environment: The resolved session environment forwarded to the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.

    Returns:
        bool: True when commits were actually pushed, False when the branch
            was already up to date.

    Raises:
        RuntimeError: When the force push fails.
    """
    command = [str(GIT["path"]), "push", "--force-with-lease", "origin", branch_name]
    exit_code, stdout, stderr = await run_command(
        command=command, target_path=target_path, environment=environment, project_id=project_id
    )
    if exit_code != 0:
        raise RuntimeError(f"Force push failed: {stderr.strip()}")
    # If push reports "Everything up-to-date", nothing was actually pushed
    if "Everything up-to-date" in stdout or "Everything up-to-date" in stderr:
        return False
    return True


async def git_cleanup(context: Context, is_success: bool, remove_worktree: bool = True) -> bool:
    """Clean up a workflow's worktree and branch after a run finishes.

    With ``remove_worktree`` set, the worktree is removed and, on failure, the
    branch is force-deleted. When it is False the worktree and the branch (which
    is checked out in it) are kept on disk, so the caller can continue the
    session's code later; nothing is removed and the cleanup counts as
    successful. The caller derives ``remove_worktree`` from the
    ``WORKTREE_CLEANUP`` flag. Research contexts run read-only in the main
    checkout with no branch or worktree, so they are skipped entirely.

    Args:
        context: The workflow context describing the worktree and branch.
        is_success: Whether the workflow completed successfully.
        remove_worktree: Whether the worktree is removed. False keeps the
            worktree and the branch.

    Returns:
        bool: True when every cleanup step succeeded, False when the worktree
            removal (or the failure-path branch deletion) failed.
    """
    if context.is_research:
        return True

    if not remove_worktree:
        print_message("Keeping worktree and branch", style="info")
        return True

    environment = context.environment
    project_id = context.project.id
    worktree_removed = True
    try:
        print_message("Removing worktree", style="heading")
        await git_worktree_remove(
            target_path=context.project.local_path,
            worktree_path=context.worktree_path,
            force=(not is_success),
            environment=environment,
            project_id=project_id,
        )
    except (OSError, RuntimeError, AttributeError):
        print_message("Failed to remove worktree", style="error")
        worktree_removed = False

    if is_success:
        return worktree_removed

    try:
        print_message("Deleting branch", style="heading")
        await git_branch_delete(
            target_path=context.project.local_path,
            branch_name=context.branch_name,
            environment=environment,
            project_id=project_id,
        )
    except (OSError, RuntimeError, AttributeError):
        print_message("Failed to delete branch", style="error")
        return False
    return worktree_removed
