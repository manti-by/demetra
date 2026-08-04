import logging
import os
from datetime import UTC, datetime
from pathlib import Path

import aiofiles
import yaml
from slugify import slugify

from demetra.library.models import Context
from demetra.services.subprocess import run_command
from demetra.settings import (
    BASE_PATH,
    GIT,
    LOG_DIR,
    WIKI_DIFF_HUNK_CAP,
    WIKI_GROQ_BUDGET_FILES,
    WIKI_GROQ_BUDGET_LINES,
)


logger = logging.getLogger(__name__)

WIKI_ROOT = (BASE_PATH / "wiki").resolve()
PAGES_ROOT = WIKI_ROOT / "pages"

FRONTMATTER_DELIMITER = "---"

PAGE_TYPE = "implementation"
PAGE_STATUS = "resolved"

LOG_TAIL_LINES = 200


def _today() -> str:
    """Return the current UTC date in ``YYYY-MM-DD`` form.

    Returns:
        str: The current date used for the wiki page filename and frontmatter.
    """
    return datetime.now(UTC).strftime("%Y-%m-%d")


def session_filename(ticket_identifier: str, title: str) -> str:
    """Derive the wiki page filename for a ticket.

    Follows the ``pages/YYYY-MM-DD-<ticket-key>-<slug>.md`` convention using the
    same slugification as ``LinearTask.slug``.

    Args:
        ticket_identifier: The Linear ticket identifier, e.g. ``MNT-147``.
        title: The Linear ticket title.

    Returns:
        str: The deterministic page filename, e.g.
            ``2026-08-04-mnt-147-wiki-processes.md``.
    """
    return f"{_today()}-{slugify(f'{ticket_identifier.strip()}-{title.strip()}')}.md"


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter delimited by ``---`` lines.

    Mirror the tolerant parsing used by the read side in ``demetra.tools.wiki``.

    Args:
        text: The full page text.

    Returns:
        dict: The parsed frontmatter mapping, or an empty dict when absent.
    """
    if not text.startswith(FRONTMATTER_DELIMITER):
        return {}
    _, sep, rest = text.partition(f"\n{FRONTMATTER_DELIMITER}")
    if not sep:
        return {}
    block = rest.split(FRONTMATTER_DELIMITER, 1)[0]
    parsed = yaml.safe_load(block)
    return parsed if isinstance(parsed, dict) else {}


def existing_page_for_ticket(ticket_identifier: str) -> Path | None:
    """Find an existing wiki page for a ticket, if any.

    Args:
        ticket_identifier: The Linear ticket identifier, e.g. ``MNT-147``.

    Returns:
        Path | None: The existing page file, or None when no page references the
            ticket.
    """
    if not PAGES_ROOT.is_dir():
        return None
    for path in sorted(PAGES_ROOT.glob("*.md")):
        try:
            meta = _parse_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if ticket_identifier in (meta.get("tickets") or []):
            return path
    return None


def _infer_services(changed_files: list[str]) -> list[str]:
    """Infer the affected ``services`` from changed file paths.

    Args:
        changed_files: The list of changed file paths.

    Returns:
        list[str]: The de-duplicated, ordered service names.
    """
    services: list[str] = []
    for path in sorted(changed_files):
        service = None
        if path.startswith("demetra/services/") and path.endswith(".py"):
            service = path.removeprefix("demetra/services/").removesuffix(".py")
        elif path == "demetra/settings.py":
            service = "settings"
        elif path.startswith("demetra") and "/" in path:
            service = path.split("/")[1]
        else:
            service = path.split("/")[0]
        if service and service not in services:
            services.append(service)
    return services


def _infer_tags(linear_task: Context) -> list[str]:
    """Infer the wiki page ``tags`` from Linear labels.

    Args:
        linear_task: The Linear task carrying ``labels``.

    Returns:
        list[str]: The de-duplicated tag list, always including ``wiki``.
    """
    tags = ["wiki"]
    for label in linear_task.labels or []:
        tag = slugify(label)
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:8]


def _session_log_tail(task_id: str) -> str:
    """Read the tail of a session's log file.

    Args:
        task_id: The Linear task identifier.

    Returns:
        str: The last ``LOG_TAIL_LINES`` lines of the session log, or an empty
            string when the log cannot be read.
    """
    session_dir = LOG_DIR if LOG_DIR.name == "sessions" else LOG_DIR / "sessions"
    log_path = session_dir / f"{task_id}.log"
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-LOG_TAIL_LINES:])


async def _git_diff_facts(target_path: Path, env: dict[str, str] | None) -> dict:
    """Collect deterministic diff facts against ``master`` for a worktree.

    Args:
        target_path: The repository worktree to diff.
        env: Optional environment overrides for the subprocess.

    Returns:
        dict: The changed file list, per-file numstat counts, total changed
            lines and the ``--stat`` text. Falls back to empty values on error.
    """
    base = [str(GIT["path"]), "diff", "master..HEAD"]
    files: list[str] = []
    numstat: list[tuple[str, str, str]] = []
    stat_text = ""
    try:
        _, name_only, _ = await run_command(
            command=[*base, "--name-only"], target_path=target_path, disable_stdio=True, env=env
        )
        files = [line for line in name_only.splitlines() if line.strip()]

        _, numstat_out, _ = await run_command(
            command=[*base, "--numstat"], target_path=target_path, disable_stdio=True, env=env
        )
        for line in numstat_out.splitlines():
            added, deleted, path = line.split("\t", 2)
            numstat.append((path, added, deleted))

        _, stat_out, _ = await run_command(
            command=[*base, "--stat"], target_path=target_path, disable_stdio=True, env=env
        )
        stat_text = stat_out.strip()
    except (OSError, AttributeError, RuntimeError, ValueError):
        logger.exception("Failed to collect git diff facts for wiki page")
        return {"files": [], "numstat": [], "changed_lines": 0, "stat_text": ""}

    changed_lines = 0
    for _, added, deleted in numstat:
        for value in (added, deleted):
            if value.isdigit():
                changed_lines += int(value)
    return {"files": files, "numstat": numstat, "changed_lines": changed_lines, "stat_text": stat_text}


async def _collect_git_diff(target_path: Path, env: dict[str, str] | None, facts: dict) -> None:
    """Populate the given facts dict with git diff data, never raising.

    Args:
        target_path: The repository worktree to diff.
        env: Optional environment overrides for the subprocess.
        facts: The facts dict mutated with ``files``/``numstat``/``changed_lines``.
    """
    diff = await _git_diff_facts(target_path=target_path, env=env)
    facts["files"] = diff["files"]
    facts["numstat"] = diff["numstat"]
    facts["changed_lines"] = diff["changed_lines"]
    facts["stat_text"] = diff["stat_text"]


def _budget_exceeded(facts: dict) -> bool:
    """Decide whether a session warrants the Groq polish pass.

    Args:
        facts: The collected session facts.

    Returns:
        bool: True when over ``WIKI_GROQ_BUDGET_FILES`` files or
            ``WIKI_GROQ_BUDGET_LINES`` changed lines.
    """
    return len(facts["files"]) > WIKI_GROQ_BUDGET_FILES or facts["changed_lines"] > WIKI_GROQ_BUDGET_LINES


def _truncate(text: str, limit: int) -> str:
    """Truncate text to a maximum length with an ellipsis marker.

    Args:
        text: The text to truncate.
        limit: The maximum number of characters.

    Returns:
        str: The possibly-truncated text.
    """
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…"


def _dump_frontmatter(meta: dict) -> str:
    """Serialize the frontmatter mapping to a ``---``-delimited YAML block.

    Args:
        meta: The frontmatter mapping.

    Returns:
        str: The YAML block with a leading and trailing ``---``.
    """

    def _inline(key: str) -> str:
        values = meta.get(key) or []
        return f"{key}: [{', '.join(values)}]" if values else f"{key}: []"

    return "\n".join(
        [
            "---",
            f"title: {meta['title']}",
            f"date: {meta['date']}",
            f"type: {meta['type']}",
            f"status: {meta['status']}",
            f"session_id: {meta['session_id'] or ''}",
            _inline("services"),
            f"branch: {meta.get('branch') or '-'}",
            _inline("tickets"),
            _inline("tags"),
            _inline("related"),
            "---",
        ]
    )


def _render_scaffold(meta: dict, facts: dict, polished: dict | None) -> str:
    """Compose the full Markdown page from the deterministic scaffold.

    Args:
        meta: The frontmatter mapping.
        facts: The collected session facts.
        polished: Optional Groq-generated ``tldr``/``overview`` values.

    Returns:
        str: The complete page Markdown.
    """
    title = meta["title"]
    tldr = (polished or {}).get("tldr")
    overview = (polished or {}).get("overview")
    if not tldr:
        tldr = f"Implementation session for {title} on branch `{meta['branch']}`."
    if not overview:
        services = ", ".join(meta["services"]) or "none"
        files = ", ".join(facts.get("files", [])[:5]) or "none"
        overview = (
            f"Changed {len(facts.get('files', []))} file(s) "
            f"({facts.get('changed_lines', 0)} lines) affecting services: {services}. "
            f"Primary files: {files}."
        )

    file_lines = "\n".join(f"- `{path}` ({added}/{deleted})" for path, added, deleted in facts.get("numstat", []))
    build_plan = (facts.get("build_plan") or "").strip() or "No build plan recorded."
    build_plan = _truncate(build_plan, WIKI_DIFF_HUNK_CAP * 4)

    return "\n".join(
        [
            _dump_frontmatter(meta),
            f"# {title}",
            "",
            "## TL;DR",
            "",
            tldr,
            "",
            "---",
            "",
            "## Overview",
            "",
            overview,
            "",
            "## Changed files",
            "",
            file_lines or "- No changed files captured.",
            "",
            "## Stat",
            "",
            f"```\n{facts.get('stat_text') or '- no stat'}\n```",
            "",
            "## Build plan",
            "",
            build_plan,
            "",
            "## Test Results",
            "",
            f"- Session status: `{meta['status']}`",
            f"- OpenCode session id: `{meta['session_id'] or '-'}`",
            "",
            "---",
            "",
            "## Follow-ups",
            "",
            "- None",
            "",
            "## References",
            "",
            f"- External: {meta.get('linear_url') or '-'}",
            "",
        ]
    )


def _index_entry(meta: dict, filename: str) -> str:
    """Build the INDEX ``## Pages`` line for a page.

    Args:
        meta: The page frontmatter mapping.
        filename: The page file name.

    Returns:
        str: A bullet line like ``- [Title](pages/file.md) — summary``.
    """
    summary = f"Implementation of {meta['title']} ({meta['date']})"
    return f"- [{meta['title']}](pages/{filename}) — {summary}"


async def _read_index() -> str:
    """Read the wiki INDEX file.

    Returns:
        str: The current ``wiki/INDEX.md`` contents, or an empty string.
    """
    index_path = WIKI_ROOT / "INDEX.md"
    if not index_path.is_file():
        return ""
    async with aiofiles.open(index_path, encoding="utf-8") as handle:
        return await handle.read()


async def _write_index(contents: str) -> None:
    """Atomically write the wiki INDEX file.

    Args:
        contents: The new ``wiki/INDEX.md`` contents.
    """
    index_path = WIKI_ROOT / "INDEX.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = index_path.with_suffix(f"{index_path.suffix}.tmp")
    async with aiofiles.open(tmp, "w", encoding="utf-8") as handle:
        await handle.write(contents)
    os.replace(tmp, index_path)


def _insert_pages_entry(contents: str, entry: str) -> str:
    """Insert a new entry at the top of the ``## Pages`` section.

    The ``## Pages`` section is newest-first; the new page is inserted
    immediately after the section header.

    Args:
        contents: The current INDEX contents.
        entry: The new bullet line.

    Returns:
        str: The updated INDEX contents.
    """
    lines = contents.splitlines()
    in_pages = False
    for index, line in enumerate(lines):
        if line.strip() == "## Pages":
            in_pages = True
            continue
        if in_pages and line.strip().startswith("## "):
            break
        if in_pages and line.startswith("- ["):
            lines.insert(index, entry)
            break
    else:
        lines.extend(["", "## Pages", "", entry])
    return "\n".join(lines)


def _find_topic_cluster(contents: str, meta: dict) -> str:
    """Return the header of the most relevant ``## By topic`` cluster.

    Scores each cluster by matching its accumulated text against the page's
    services and tags; returns the highest-scoring header, falling back to the
    first cluster when none matches.

    Args:
        contents: The current INDEX contents.
        meta: The page frontmatter mapping.

    Returns:
        str: The cluster header (without its page count suffix if present).
    """
    terms = [str(term).casefold() for term in (meta.get("services") or []) + (meta.get("tags") or [])]
    best_header = None
    best_score = -1
    current_header = None
    for line in contents.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            current_header = stripped
        elif stripped.startswith("- [") and current_header:
            score = sum(stripped.casefold().count(term) for term in terms)
            if score > best_score:
                best_score = score
                best_header = current_header
    if best_score > 0 and best_header:
        return best_header
    for line in contents.splitlines():
        if line.strip().startswith("### "):
            return line.strip()
    return "### Workflow orchestration & agents"


def _insert_cluster_entry(contents: str, cluster_header: str, entry: str) -> str:
    """Append a page bullet under a ``## By topic`` cluster.

    Args:
        contents: The current INDEX contents.
        cluster_header: The target cluster header line.
        entry: The bullet line to append.

    Returns:
        str: The updated INDEX contents.
    """
    target = cluster_header.split(" (", 1)[0]
    lines = contents.splitlines()
    in_cluster = False
    for index, line in enumerate(lines):
        if line.strip().startswith("### ") and line.split(" (", 1)[0] == target:
            in_cluster = True
            continue
        if in_cluster and line.strip().startswith("### "):
            lines.insert(index, entry)
            break
        if in_cluster and index == len(lines) - 1:
            lines.append(entry)
            break
    else:
        return contents
    return "\n".join(lines)


async def _patch_index(meta: dict, filename: str) -> None:
    """Update ``INDEX.md`` with a new page entry.

    Inserts the entry into ``## Pages`` (newest-first) and appends a bullet
    under the best-matching ``## By topic`` cluster.

    Args:
        meta: The page frontmatter mapping.
        filename: The page file name.
    """
    contents = await _read_index()
    pages_entry = _index_entry(meta=meta, filename=filename)
    updated = _insert_pages_entry(contents=contents, entry=pages_entry)
    cluster = _find_topic_cluster(contents=updated, meta=meta)
    cluster_entry = f"- [{meta['title']}](pages/{filename}) — {meta['date']}"
    updated = _insert_cluster_entry(contents=updated, cluster_header=cluster, entry=cluster_entry)
    await _write_index(contents=updated)


async def _write_page(path: Path, body: str) -> None:
    """Atomically write a wiki page file.

    Args:
        path: The target page path.
        body: The page Markdown body.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    async with aiofiles.open(tmp, "w", encoding="utf-8") as handle:
        await handle.write(body)
    os.replace(tmp, path)


def collect_session_facts(context: Context) -> dict:
    """Gather the deterministic facts a wiki page is built from.

    Args:
        context: The workflow context.

    Returns:
        dict: The session facts keyed for scaffold rendering, including the git
            diff summary against ``master``.
    """
    linear_task = context.linear_task
    facts: dict = {
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
        "log_tail": _session_log_tail(task_id=linear_task.id),
        "task_id": linear_task.id,
    }
    return facts


async def write_session_wiki_page(context: Context) -> None:
    """Write (or update) the wiki page for the current session.

    Failures are logged and never raised so a wiki error cannot fail the
    workflow.

    Args:
        context: The workflow context.
    """
    try:
        facts = collect_session_facts(context=context)
        identifier = facts["ticket_identifier"]
        title = facts["title"]

        existing = existing_page_for_ticket(ticket_identifier=identifier)
        filename = existing.name if existing is not None else session_filename(identifier=identifier, title=title)
        related = [existing.name] if existing is not None else []

        from demetra.services.wiki import _budget_exceeded  # noqa: PLC0415

        facts["diff"] = {}
        await _collect_git_diff(target_path=context.worktree_path, env=context.project.environment, facts=facts)

        meta = {
            "title": f"{identifier}: {title}",
            "date": _today(),
            "type": PAGE_TYPE,
            "status": PAGE_STATUS,
            "session_id": facts["session_id"] or "",
            "services": _infer_services(facts.get("files", [])),
            "branch": facts["branch"],
            "tickets": [identifier],
            "tags": _infer_tags(linear_task=context.linear_task),
            "related": related,
            "linear_url": facts["url"] or "-",
        }

        polished: dict | None = None
        if _budget_exceeded(facts=facts):
            from demetra.services.groq import summarize_session

            polished = await summarize_session(
                ticket_text=context.linear_task.text,
                description=facts["description"],
                build_plan=facts["build_plan"] or "",
                diff_summary=facts.get("stat_text") or "",
            )

        body = _render_scaffold(meta=meta, facts=facts, polished=polished)
        await _write_page(path=PAGES_ROOT / filename, body=body)
        await _patch_index(meta=meta, filename=filename)
        logger.info("Wrote wiki page %s for ticket %s", filename, identifier)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to write wiki page for session; wiki failure is non-fatal")
