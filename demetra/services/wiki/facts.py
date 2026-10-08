import re
from collections import deque
from pathlib import Path

import demetra.services.wiki as service
from demetra.library.models import Context, SessionEnvironment


def session_log_tail(task_id: str) -> str:
    """Read the tail of a session's log file.

    Streams the file line-by-line into a bounded deque so verbose build logs do
    not spike memory. The task id is sanitized of path separators so a
    malformed id cannot escape the log directory.

    Args:
        task_id: The Linear task identifier.

    Returns:
        str: The last ``LOG_TAIL_LINES`` lines of the session log, or an empty
            string when the log cannot be read.
    """
    session_dir = service.LOG_DIR if service.LOG_DIR.name == "sessions" else service.LOG_DIR / "sessions"
    safe_task_id = re.sub(r"[\\/]", "_", task_id)
    log_path = session_dir / f"{safe_task_id}.log"
    tail: deque[str] = deque(maxlen=service.LOG_TAIL_LINES)
    try:
        with open(log_path, encoding="utf-8") as handle:
            for line in handle:
                tail.append(line.rstrip("\n"))
    except OSError:
        return ""
    return "\n".join(tail)


async def git_default_branch(target_path: Path, environment: SessionEnvironment | None = None) -> str:
    """Resolve the remote-tracking default branch for a worktree.

    Reads ``refs/remotes/origin/HEAD``; falls back to ``"origin/master"`` when
    the symbolic ref is missing or the lookup fails.

    Args:
        target_path: The repository worktree.
        environment: The resolved session environment forwarded to the subprocess.

    Returns:
        str: The remote-tracking default branch ref, e.g. ``"origin/main"``.
    """
    command = [str(service.GIT["path"]), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"]
    try:
        exit_code, stdout, _ = await service.run_command(
            command=command, target_path=target_path, disable_stdio=True, environment=environment
        )
    except (OSError, RuntimeError):
        return "origin/master"
    if exit_code != 0:
        return "origin/master"
    branch = stdout.strip()
    if not branch:
        return "origin/master"
    if branch.startswith("origin/"):
        return branch
    return f"origin/{branch.removeprefix('refs/remotes/origin/')}"


async def git_diff_facts(target_path: Path, environment: SessionEnvironment | None = None) -> dict:
    """Collect deterministic diff facts against the default branch for a worktree.

    Diffs the working tree against the default branch so uncommitted changes
    (e.g. the build agent output before the commit step) are captured. Besides
    the file list and the ``--stat`` text it returns a bounded excerpt of the
    unified diff so the page author can quote real code and cite
    ``file:line`` instead of inventing both.

    Args:
        target_path: The repository worktree to diff.
        environment: The resolved session environment forwarded to the subprocess.

    Returns:
        dict: The changed file list, the ``--stat`` text and the bounded
            ``excerpt_text``. Falls back to empty values on error.
    """
    base_ref = await service.git_default_branch(target_path=target_path, environment=environment)
    base = [str(service.GIT["path"]), "diff", base_ref]
    files: list[str] = []
    stat_text = ""
    excerpt_text = ""
    try:
        exit_code, name_only, name_only_err = await service.run_command(
            command=[*base, "--name-only"], target_path=target_path, disable_stdio=True, environment=environment
        )
        if exit_code != 0:
            raise RuntimeError(f"git diff --name-only failed: {name_only_err.strip()}")
        files = [line for line in name_only.splitlines() if line.strip()]

        exit_code, stat_out, stat_err = await service.run_command(
            command=[*base, "--stat"], target_path=target_path, disable_stdio=True, environment=environment
        )
        if exit_code != 0:
            raise RuntimeError(f"git diff --stat failed: {stat_err.strip()}")
        stat_text = stat_out.strip()

        excerpt_text = await git_diff_excerpt(target_path=target_path, environment=environment, base_ref=base_ref)
    except (OSError, AttributeError, RuntimeError, ValueError):
        service.logger.exception("Failed to collect git diff facts for wiki page")
        return {"files": [], "stat_text": "", "excerpt_text": ""}

    return {"files": files, "stat_text": stat_text, "excerpt_text": excerpt_text}


async def git_diff_excerpt(
    target_path: Path,
    environment: SessionEnvironment | None = None,
    base_ref: str | None = None,
) -> str:
    """Read a bounded excerpt of the unified diff for a worktree.

    Hunks are emitted with zero context so the excerpt carries the changed lines
    and their ``@@`` line numbers, and the whole excerpt is capped at
    ``WIKI_DIFF_HUNK_CAP`` lines to keep the prompt bounded. Empty when the diff
    cannot be read; a failure here never blocks the page.

    Args:
        target_path: The repository worktree to diff.
        environment: The resolved session environment forwarded to the subprocess.
        base_ref: The already-resolved base ref, avoiding a second lookup.

    Returns:
        str: The truncated unified diff text, or an empty string.
    """
    resolved_base = base_ref or await service.git_default_branch(target_path=target_path, environment=environment)
    command = [str(service.GIT["path"]), "diff", resolved_base, "--unified=0"]
    try:
        exit_code, stdout, stderr = await service.run_command(
            command=command, target_path=target_path, disable_stdio=True, environment=environment
        )
    except (OSError, RuntimeError):
        service.logger.exception("Failed to read the git diff excerpt for the wiki page")
        return ""
    if exit_code != 0:
        service.logger.warning("git diff excerpt failed: %s", stderr.strip())
        return ""
    lines = stdout.strip().splitlines()
    cap = service.WIKI["diff_hunk_cap"]
    if len(lines) <= cap:
        return "\n".join(lines)
    service.logger.warning("Truncated the git diff excerpt from %d to %d lines", len(lines), cap)
    return "\n".join([*lines[:cap], "... (diff excerpt truncated)"])


def collect_session_facts(context: Context) -> dict:
    """Gather the deterministic facts a wiki page is built from.

    Args:
        context: The workflow context.

    Returns:
        dict: The session facts keyed for page composition, including the git
            diff summary against the default branch.
    """
    linear_task = context.linear_task
    return {
        "ticket_identifier": linear_task.identifier,
        "title": linear_task.title,
        "description": linear_task.description,
        "url": linear_task.url,
        "labels": linear_task.labels,
        "branch": context.branch_name,
        "worktree_path": context.worktree_path,
        "build_plan": service.truncate(text=context.build_plan or "", limit=service.WIKI["build_plan_cap"]),
        "session_id": context.session_id,
        "pr_link": context.session.pr_link if context.session is not None else None,
        "task_id": linear_task.id,
        "log_tail": service.session_log_tail(task_id=linear_task.id),
    }
