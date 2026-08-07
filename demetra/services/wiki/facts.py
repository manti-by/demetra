import re
from collections import deque
from pathlib import Path

import demetra.services.wiki as service
from demetra.library.models import Context


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


async def git_default_branch(target_path: Path, env: dict[str, str] | None) -> str:
    """Resolve the remote-tracking default branch for a worktree.

    Reads ``refs/remotes/origin/HEAD``; falls back to ``"origin/master"`` when
    the symbolic ref is missing or the lookup fails.

    Args:
        target_path: The repository worktree.
        env: Optional environment overrides for the subprocess.

    Returns:
        str: The remote-tracking default branch ref, e.g. ``"origin/main"``.
    """
    command = [str(service.GIT["path"]), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"]
    try:
        exit_code, stdout, _ = await service.run_command(
            command=command, target_path=target_path, disable_stdio=True, env=env
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


async def git_diff_facts(target_path: Path, env: dict[str, str] | None) -> dict:
    """Collect deterministic diff facts against the default branch for a worktree.

    Args:
        target_path: The repository worktree to diff.
        env: Optional environment overrides for the subprocess.

    Returns:
        dict: The changed file list, per-file numstat counts, total changed
            lines and the ``--stat`` text. Falls back to empty values on error.
    """
    base_ref = await service.git_default_branch(target_path=target_path, env=env)
    base = [str(service.GIT["path"]), "diff", f"{base_ref}..HEAD"]
    files: list[str] = []
    numstat: list[tuple[str, str, str]] = []
    stat_text = ""
    try:
        exit_code, name_only, name_only_err = await service.run_command(
            command=[*base, "--name-only"], target_path=target_path, disable_stdio=True, env=env
        )
        if exit_code != 0:
            raise RuntimeError(f"git diff --name-only failed: {name_only_err.strip()}")
        files = [line for line in name_only.splitlines() if line.strip()]

        exit_code, numstat_out, numstat_err = await service.run_command(
            command=[*base, "--numstat"], target_path=target_path, disable_stdio=True, env=env
        )
        if exit_code != 0:
            raise RuntimeError(f"git diff --numstat failed: {numstat_err.strip()}")
        for line in numstat_out.splitlines():
            added, deleted, path = line.split("\t", 2)
            numstat.append((path, added, deleted))

        exit_code, stat_out, stat_err = await service.run_command(
            command=[*base, "--stat"], target_path=target_path, disable_stdio=True, env=env
        )
        if exit_code != 0:
            raise RuntimeError(f"git diff --stat failed: {stat_err.strip()}")
        stat_text = stat_out.strip()
    except (OSError, AttributeError, RuntimeError, ValueError):
        service.logger.exception("Failed to collect git diff facts for wiki page")
        return {"files": [], "numstat": [], "changed_lines": 0, "stat_text": ""}

    changed_lines = 0
    for _, added, deleted in numstat:
        for value in (added, deleted):
            if value.isdigit():
                changed_lines += int(value)
    return {"files": files, "numstat": numstat, "changed_lines": changed_lines, "stat_text": stat_text}


def budget_exceeded(facts: dict) -> bool:
    """Decide whether a session warrants the Groq polish pass.

    Args:
        facts: The collected session facts.

    Returns:
        bool: True when over ``WIKI_GROQ_BUDGET_FILES`` files or
            ``WIKI_GROQ_BUDGET_LINES`` changed lines.
    """
    return (
        len(facts["files"]) > service.WIKI_GROQ_BUDGET_FILES or facts["changed_lines"] > service.WIKI_GROQ_BUDGET_LINES
    )


def collect_session_facts(context: Context) -> dict:
    """Gather the deterministic facts a wiki page is built from.

    Args:
        context: The workflow context.

    Returns:
        dict: The session facts keyed for scaffold rendering, including the git
            diff summary against ``master``.
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
        "build_plan": context.build_plan,
        "session_id": context.session_id,
        "pr_link": context.session.pr_link if context.session is not None else None,
        "task_id": linear_task.id,
        "log_tail": service.session_log_tail(task_id=linear_task.id),
    }
