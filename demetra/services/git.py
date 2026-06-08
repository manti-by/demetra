from pathlib import Path

from demetra.library.models import Context, Project
from demetra.services.subprocess import run_command
from demetra.services.tui import print_message
from demetra.settings import GIT


def get_worktree_path(project: Project, branch_name: str) -> Path:
    return GIT["worktree_path"] / project.repository_owner / project.repository_name / branch_name


async def git_worktree_create(project: Project, branch_name: str, env: dict[str, str] | None = None) -> Path:
    import shutil

    worktree_path = get_worktree_path(project=project, branch_name=branch_name)
    if worktree_path.exists():
        git_file = worktree_path / ".git"
        if git_file.exists() and git_file.is_file():
            await git_worktree_remove(target_path=project.local_path, worktree_path=worktree_path, force=True, env=env)
        else:
            shutil.rmtree(worktree_path)
        await git_branch_delete(target_path=project.local_path, branch_name=branch_name, env=env)

    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    command = [str(GIT["path"]), "worktree", "add", "-b", branch_name, str(worktree_path)]
    exit_code, _, stderr = await run_command(command=command, target_path=project.local_path, env=env)
    if exit_code != 0:
        raise RuntimeError(f"Failed to create worktree at {worktree_path}: {stderr.strip() or 'unknown error'}")
    return worktree_path


async def git_worktree_remove(
    target_path: Path, worktree_path: Path, force: bool = False, env: dict[str, str] | None = None
):
    command = [str(GIT["path"]), "worktree", "remove", str(worktree_path)]
    if force:
        command.append("--force")
    exit_code, _, stderr = await run_command(command=command, target_path=target_path, env=env)
    if exit_code != 0:
        raise RuntimeError(f"Failed to remove worktree {worktree_path}: {stderr.strip() or 'unknown error'}")


async def git_add_all(target_path: Path, env: dict[str, str] | None = None):
    command = [str(GIT["path"]), "add", "."]
    await run_command(command=command, target_path=target_path, env=env)

    diff_cmd = [str(GIT["path"]), "diff", "--staged", "--name-only"]
    _, stdout, _ = await run_command(command=diff_cmd, target_path=target_path, disable_stdio=True, env=env)
    if not stdout.strip():
        raise RuntimeError("No files to commit")


async def git_commit(target_path: Path, message: str, env: dict[str, str] | None = None):
    command = [str(GIT["path"]), "commit", "-m", message]
    await run_command(command=command, target_path=target_path, env=env)


async def git_pull(target_path: Path, branch_name: str = "master", env: dict[str, str] | None = None):
    command = [str(GIT["path"]), "pull", "origin", branch_name]
    await run_command(command=command, target_path=target_path, env=env)


async def git_push(target_path: Path, branch_name: str, env: dict[str, str] | None = None):
    command = [str(GIT["path"]), "push", "--set-upstream", "origin", branch_name]
    await run_command(command=command, target_path=target_path, env=env)


async def git_branch_delete(target_path: Path, branch_name: str, env: dict[str, str] | None = None):
    command = [str(GIT["path"]), "branch", "-D", branch_name]
    await run_command(command=command, target_path=target_path, env=env)


async def git_cleanup(context: Context, is_success: bool):
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
