import logging
import os
import re
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

import aiofiles
import yaml
from slugify import slugify

from demetra.library.models import Context, LinearTask
from demetra.services.groq import summarize_session
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

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
BARE_DASH_RE = re.compile(r"^(\s*[A-Za-z_][\w]*\s*:\s*)-$", re.MULTILINE)

PAGE_TYPE = "implementation"
PAGE_STATUS = "resolved"

LOG_TAIL_LINES = 200

INDEX_PATH = WIKI_ROOT / "INDEX.md"
QUESTIONS_PATH = WIKI_ROOT / "QUESTIONS.md"
AGENTS_PATH = BASE_PATH / "AGENTS.md"

AGENTS_DRIFT_ANCHORS = (
    "demetra/services/wiki.py",
    "demetra/tools/wiki.py",
    "uv.lock",
    "Linear",
    "GitHub",
    "Groq",
    "never prefix with",
)


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


def parse_page_file(path: Path) -> dict | None:
    """Parse a wiki page file into metadata and body content.

    Reads YAML frontmatter delimited by ``---`` lines; pages with invalid or
    non-mapping frontmatter are skipped with a warning. This is the shared
    parser used by both the read-side MCP tools and the write-side service.

    Args:
        path: Path of the ``.md`` page file.

    Returns:
        dict | None: A mapping with ``name``, ``meta`` and ``body`` keys, or
            None when the frontmatter cannot be parsed.
    """
    text = path.read_text(encoding="utf-8")
    meta: dict = {}
    body = text
    match = FRONTMATTER_RE.match(text)
    if match:
        block = BARE_DASH_RE.sub(r'\1"-"', match.group(1))
        try:
            parsed = yaml.safe_load(block)
        except yaml.YAMLError:
            logger.warning(f"Skipping page with invalid frontmatter: {path.name}")
            return None
        if parsed is not None and not isinstance(parsed, dict):
            logger.warning(f"Skipping page with non-mapping frontmatter: {path.name}")
            return None
        meta = parsed or {}
        body = text[match.end() :]
    return {"name": path.name, "meta": meta, "body": body}


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


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter delimited by ``---`` lines.

    Tolerant mirror of the read side used for quick ticket lookups.

    Args:
        text: The full page text.

    Returns:
        dict: The parsed frontmatter mapping, or an empty dict when absent.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    block = BARE_DASH_RE.sub(r'\1"-"', match.group(1))
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


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
            service = Path(path).stem
        if service and service not in services:
            services.append(service)
    return services


def _infer_tags(linear_task: LinearTask) -> list[str]:
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

    Streams the file line-by-line into a bounded deque so verbose build logs do
    not spike memory. The task id is sanitized of path separators so a
    malformed id cannot escape the log directory.

    Args:
        task_id: The Linear task identifier.

    Returns:
        str: The last ``LOG_TAIL_LINES`` lines of the session log, or an empty
            string when the log cannot be read.
    """
    session_dir = LOG_DIR if LOG_DIR.name == "sessions" else LOG_DIR / "sessions"
    safe_task_id = re.sub(r"[\\/]", "_", task_id)
    log_path = session_dir / f"{safe_task_id}.log"
    tail: deque[str] = deque(maxlen=LOG_TAIL_LINES)
    try:
        with open(log_path, encoding="utf-8") as handle:
            for line in handle:
                tail.append(line.rstrip("\n"))
    except OSError:
        return ""
    return "\n".join(tail)


async def _default_branch(target_path: Path, env: dict[str, str] | None) -> str:
    """Resolve the remote default branch for a worktree.

    Reads ``origin/HEAD``; falls back to ``"master"`` when the symbolic ref is
    missing or the lookup fails.

    Args:
        target_path: The repository worktree.
        env: Optional environment overrides for the subprocess.

    Returns:
        str: The default branch name, e.g. ``"main"``.
    """
    command = [str(GIT["path"]), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"]
    try:
        _, stdout, _ = await run_command(command=command, target_path=target_path, disable_stdio=True, env=env)
    except (OSError, RuntimeError):
        return "master"
    branch = stdout.strip().removeprefix("origin/")
    return branch or "master"


async def _git_diff_facts(target_path: Path, env: dict[str, str] | None) -> dict:
    """Collect deterministic diff facts against the default branch for a worktree.

    Args:
        target_path: The repository worktree to diff.
        env: Optional environment overrides for the subprocess.

    Returns:
        dict: The changed file list, per-file numstat counts, total changed
            lines and the ``--stat`` text. Falls back to empty values on error.
    """
    base_ref = await _default_branch(target_path=target_path, env=env)
    base = [str(GIT["path"]), "diff", f"{base_ref}..HEAD"]
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


def _yaml_scalar(value: object) -> str:
    """Quote a YAML scalar when it needs quoting.

    Titles like ``MNT-147: Wiki processes`` contain ``: `` and break bare
    scalar parsing, so any value with YAML-significant characters is quoted.

    Args:
        value: The scalar value to render.

    Returns:
        str: The value, quoted when necessary.
    """
    if value is None:
        return ""
    text = str(value)
    if not text:
        return ""
    if any(character in text for character in (":", "#", "[", "]", "{", "}", '"', "'", "`", "*", "&", "\\")):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


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
            f"title: {_yaml_scalar(meta.get('title') or '')}",
            f"date: {_yaml_scalar(meta.get('date') or '')}",
            f"type: {_yaml_scalar(meta.get('type') or '')}",
            f"status: {_yaml_scalar(meta.get('status') or '')}",
            f"session_id: {_yaml_scalar(meta.get('session_id') or '')}",
            _inline("services"),
            f"branch: {_yaml_scalar(meta.get('branch') or '-')}",
            _inline("tickets"),
            _inline("tags"),
            _inline("related"),
            "---",
        ]
    )


def render_wiki_page(meta: dict, facts: dict, polished_summary: dict | None = None) -> str:
    """Compose the full Markdown page from the deterministic scaffold.

    Args:
        meta: The frontmatter mapping.
        facts: The collected session facts.
        polished_summary: Optional Groq-generated ``tldr``/``overview`` values.

    Returns:
        str: The complete page Markdown.
    """
    title = meta["title"]
    tldr = (polished_summary or {}).get("tldr")
    overview = (polished_summary or {}).get("overview")
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
    if not INDEX_PATH.is_file():
        return ""
    async with aiofiles.open(INDEX_PATH, encoding="utf-8") as handle:
        return await handle.read()


async def _write_index(contents: str) -> None:
    """Atomically write the wiki INDEX file.

    Args:
        contents: The new ``wiki/INDEX.md`` contents.
    """
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = INDEX_PATH.with_suffix(f"{INDEX_PATH.suffix}.tmp")
    async with aiofiles.open(tmp, "w", encoding="utf-8") as handle:
        await handle.write(contents)
    os.replace(tmp, INDEX_PATH)


def _insert_pages_entry(contents: str, entry: str) -> str:
    """Insert a new entry at the top of the ``## Pages`` section.

    The ``## Pages`` section is newest-first; the new page is inserted
    immediately after the section header. Idempotent: an identical entry is
    left untouched.

    Args:
        contents: The current INDEX contents.
        entry: The new bullet line.

    Returns:
        str: The updated INDEX contents.
    """
    if entry in contents:
        return contents
    lines = contents.splitlines()
    in_pages = False
    insert_at = None
    for index, line in enumerate(lines):
        if line.strip() == "## Pages":
            in_pages = True
            insert_at = index + 1
            continue
        if in_pages and line.strip().startswith("## "):
            if insert_at is not None:
                lines.insert(insert_at, entry)
            break
        if in_pages and line.startswith("- ["):
            lines.insert(index, entry)
            break
        if in_pages and insert_at is not None:
            insert_at = index + 1
    else:
        if in_pages and insert_at is not None:
            lines.insert(insert_at, entry)
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

    Idempotent: an identical entry is left untouched.

    Args:
        contents: The current INDEX contents.
        cluster_header: The target cluster header line.
        entry: The bullet line to append.

    Returns:
        str: The updated INDEX contents.
    """
    if entry in contents:
        return contents
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
    under the best-matching ``## By topic`` cluster. When the index has no
    ``## By topic`` section yet, it is regenerated from the page catalog first
    so the cluster insert has a target.

    Args:
        meta: The page frontmatter mapping.
        filename: The page file name.
    """
    contents = await _read_index()
    pages_entry = _index_entry(meta=meta, filename=filename)
    updated = _insert_pages_entry(contents=contents, entry=pages_entry)
    if "## By topic" not in updated:
        await _regenerate_by_topic()
        updated = await _read_index()
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
        "log_tail": _session_log_tail(task_id=linear_task.id),
    }


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
        filename = (
            existing.name if existing is not None else session_filename(ticket_identifier=identifier, title=title)
        )
        related: list[str] = []
        if existing is not None:
            try:
                existing_meta = _parse_frontmatter(existing.read_text(encoding="utf-8"))
            except OSError:
                existing_meta = {}
            related = [item for item in (existing_meta.get("related") or []) if item != filename]

        diff = await _git_diff_facts(target_path=context.worktree_path, env=context.project.environment)
        facts["files"] = diff["files"]
        facts["numstat"] = diff["numstat"]
        facts["changed_lines"] = diff["changed_lines"]
        facts["stat_text"] = diff["stat_text"]

        meta = {
            "title": f"{identifier}: {title}",
            "date": _today(),
            "type": PAGE_TYPE,
            "status": PAGE_STATUS,
            "session_id": facts["session_id"] or "",
            "services": _infer_services(facts["files"]),
            "branch": facts["branch"],
            "tickets": [identifier],
            "tags": _infer_tags(linear_task=context.linear_task),
            "related": related,
            "linear_url": facts["url"] or "-",
        }

        polished_summary: dict | None = None
        if _budget_exceeded(facts=facts):
            polished_summary = await summarize_session(
                ticket_text=context.linear_task.text,
                description=facts["description"],
                build_plan=facts["build_plan"] or "",
                diff_summary=facts["stat_text"] or "",
            )

        body = render_wiki_page(meta=meta, facts=facts, polished_summary=polished_summary)
        await _write_page(path=PAGES_ROOT / filename, body=body)
        await _patch_index(meta=meta, filename=filename)
        logger.info("Wrote wiki page %s for ticket %s", filename, identifier)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to write wiki page for session; wiki failure is non-fatal")


DEDUP_SIMILARITY_THRESHOLD = 0.85

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Workflow orchestration & agents": (
        "workflow",
        "plan",
        "build",
        "review",
        "agent",
        "resolve",
        "question",
        "opencode",
    ),
    "Sessions, status & resume": ("session", "status", "resume", "step", "history", "websocket"),
    "React frontend / UI": ("react", "frontend", "ui", "component", "vite", "favicon"),
    "Linear & GitHub integrations": ("linear", "github", "pr", "notification", "listener", "oauth"),
    "Authentication & API security": ("auth", "password", "cookie", "cors", "jwt", "bcrypt", "security"),
    "Database & migrations": ("database", "migration", "sqlalchemy", "postgres", "alembic"),
    "Context, tokens & compaction": ("context", "token", "compaction", "compression"),
    "Logging infrastructure": ("log", "ansi", "logging"),
    "MCP / integrations": ("mcp", "tool", "wiki"),
    "Testing & tooling": ("test", "pytest", "ruff", "lint", "feature flag"),
    "Docs, feature flags & release tooling": ("agents.md", "docs", "release", "version", "flag"),
    "Deploy & infrastructure": ("deploy", "systemd", "nginx", "docker", "infrastructure"),
    "Subprocess & timeouts": ("subprocess", "timeout", "shell"),
    "Git & worktrees": ("git", "worktree", "branch", "merge", "rebase"),
    "TUI & CLI": ("tui", "cli", "terminal", "rich"),
}


def _page_tokens(meta: dict, body: str) -> set[str]:
    """Split a page's metadata and body into a token set for dedup scoring.

    Args:
        meta: The page frontmatter mapping.
        body: The page body text.

    Returns:
        set[str]: The lowercase token set of title, tags, tickets and body.
    """
    text = " ".join(
        [
            str(meta.get("title") or ""),
            " ".join(str(item) for item in (meta.get("tags") or [])),
            " ".join(str(item) for item in (meta.get("tickets") or [])),
            body,
        ]
    )
    return {token for token in re.findall(r"[a-z0-9]+", text.casefold()) if len(token) > 2}


def _similarity(left: set[str], right: set[str]) -> float:
    """Compute the Jaccard similarity of two token sets.

    Args:
        left: The first token set.
        right: The second token set.

    Returns:
        float: The Jaccard similarity in ``[0, 1]``.
    """
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


async def _answer_sweep() -> int:
    """Apply answered ``## Open`` entries in QUESTIONS.md and move them to Resolved.

    Returns:
        int: The number of questions resolved.
    """
    if not QUESTIONS_PATH.is_file():
        return 0
    text = QUESTIONS_PATH.read_text(encoding="utf-8")
    if "## Open" not in text:
        return 0

    header, _, rest = text.partition("## Open")
    open_block, _, resolved_block = rest.partition("## Resolved")

    kept: list[str] = []
    resolved: list[str] = []
    current: list[str] = []
    count = 0
    for line in open_block.splitlines():
        if line.strip().startswith("### "):
            if current:
                entry_text = "\n".join(current)
                if _has_answer(entry_text):
                    count += 1
                    resolved.append(entry_text)
                else:
                    kept.append(entry_text)
            current = [line]
        else:
            current.append(line)
    if current:
        entry_text = "\n".join(current)
        if _has_answer(entry_text):
            count += 1
            resolved.append(entry_text)
        else:
            kept.append(entry_text)

    if not count:
        return 0

    open_section = "\n\n".join(kept)
    resolved_section = (
        "\n\n".join([*resolved, resolved_block.strip()]) if resolved_block.strip() else "\n\n".join(resolved)
    )
    new_text = (
        f"{header}## Open\n\n{open_section}\n\n## Resolved\n\n{resolved_section}\n"
        if open_section.strip()
        else f"{header}## Open\n\n_Newest first._\n\n## Resolved\n\n{resolved_section}\n"
    )
    QUESTIONS_PATH.write_text(encoding="utf-8", data=new_text)
    return count


def _has_answer(entry_text: str) -> bool:
    """Check whether a question entry has a filled-in answer.

    A question counts as answered only when the ``**Answer:**`` field holds
    non-whitespace content beyond the template placeholder.

    Args:
        entry_text: The raw question entry text.

    Returns:
        bool: True when the ``**Answer:**`` field holds real content.
    """
    if "**Answer:**" not in entry_text:
        return False
    _, _, value = entry_text.partition("**Answer:**")
    answer = value.strip().lstrip("*").strip()
    if not answer:
        return False
    if re.search(r"^(?:\(?_|_?\(|left blank)", answer):
        return False
    return True


async def _dedup_pages() -> tuple[int, int]:
    """Merge near-duplicate wiki pages keeping the most recent version.

    Returns:
        tuple[int, int]: The number of pages merged and deleted.
    """
    if not PAGES_ROOT.is_dir():
        return 0, 0
    parsed: dict[Path, dict] = {}
    for path in sorted(PAGES_ROOT.glob("*.md")):
        page = parse_page_file(path)
        if page is not None:
            parsed[path] = page

    merged = 0
    deleted: list[Path] = []
    candidates = list(parsed)
    for index, left_path in enumerate(candidates):
        if left_path in deleted:
            continue
        for right_path in candidates[index + 1 :]:
            if right_path in deleted:
                continue
            left, right = parsed[left_path], parsed[right_path]
            tokens_left = _page_tokens(left["meta"], left["body"])
            tokens_right = _page_tokens(right["meta"], right["body"])
            if _similarity(tokens_left, tokens_right) < DEDUP_SIMILARITY_THRESHOLD:
                continue
            survivor = _pick_survivor(left_path=left_path, right_path=right_path)
            if survivor is None:
                continue
            survivor_path, loser_path = survivor
            merged += 1
            if _merge_page_content(survivor_path=survivor_path, loser_path=loser_path, parsed=parsed):
                deleted.append(loser_path)
                refreshed = parse_page_file(survivor_path)
                if refreshed is not None:
                    parsed[survivor_path] = refreshed

    for path in deleted:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning(f"Failed to delete duplicate wiki page {path.name}")
    return merged, len(deleted)


def _pick_survivor(left_path: Path, right_path: Path) -> tuple[Path, Path] | None:
    """Pick the survivor of a near-duplicate pair by frontmatter date.

    Args:
        left_path: The first page path.
        right_path: The second page path.

    Returns:
        tuple[Path, Path] | None: The ``(survivor, loser)`` paths, or None when
            both dates are equal.
    """
    left_date = _page_date(left_path)
    right_date = _page_date(right_path)
    if left_date == right_date:
        return None
    if left_date > right_date:
        return left_path, right_path
    return right_path, left_path


def _page_date(path: Path) -> str:
    """Return the frontmatter ``date`` of a page, defaulting to its filename date.

    Args:
        path: The page path.

    Returns:
        str: The page date in ``YYYY-MM-DD`` form.
    """
    try:
        meta = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("date"):
            return str(meta["date"])
    except (OSError, yaml.YAMLError):
        pass
    match = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
    return match.group(1) if match else "0000-00-00"


def _merge_page_content(survivor_path: Path, loser_path: Path, parsed: dict) -> bool:
    """Merge a duplicate page's frontmatter lists and body into the survivor.

    Args:
        survivor_path: The surviving page path.
        loser_path: The page to merge in.
        parsed: The parsed pages mapping used to read frontmatter.

    Returns:
        bool: True when the survivor was written successfully, False when the
            write failed and the loser must not be deleted.
    """
    survivor = parsed[survivor_path]
    loser = parsed[loser_path]
    survivor_meta = dict(survivor["meta"])
    loser_meta = loser["meta"]
    for key in ("tags", "related", "tickets", "services"):
        union = list(dict.fromkeys([*(survivor_meta.get(key) or []), *(loser_meta.get(key) or [])]))
        if loser_path.name in union:
            union.remove(loser_path.name)
        survivor_meta[key] = union

    survivor_body = survivor["body"]
    loser_body = loser["body"]
    merged_body = survivor_body
    for section in re.split(r"(?=^#{1,3} )", loser_body, flags=re.MULTILINE):
        if section.strip() and section.strip() not in survivor_body:
            merged_body = f"{merged_body.rstrip()}\n\n{section.strip()}"
    survivor_meta["related"] = [item for item in (survivor_meta.get("related") or []) if item != loser_path.name]

    body = _dump_frontmatter(survivor_meta) + "\n" + merged_body.lstrip()
    try:
        survivor_path.write_text(encoding="utf-8", data=body)
    except OSError:
        logger.warning(f"Failed to write merged wiki page {survivor_path.name}")
        return False
    return True


def _cluster_for(meta: dict) -> str:
    """Assign a page to a ``## By topic`` cluster by keyword scoring.

    Args:
        meta: The page frontmatter mapping.

    Returns:
        str: The best-matching cluster title, or ``"Other"`` when none matches.
    """
    haystack = (
        f"{meta.get('title') or ''} "
        f"{' '.join(str(item) for item in (meta.get('services') or []))} "
        f"{' '.join(str(item) for item in (meta.get('tags') or []))}"
    ).casefold()
    best = ("Other", 0)
    for cluster, keywords in TOPIC_KEYWORDS.items():
        score = sum(haystack.count(keyword) for keyword in keywords)
        if score > best[1]:
            best = (cluster, score)
    return best[0]


async def _regenerate_by_topic() -> int:
    """Rebuild the ``## By topic`` section of INDEX.md from page frontmatter.

    Returns:
        int: The number of topic clusters written.
    """
    if not PAGES_ROOT.is_dir():
        return 0
    clusters: dict[str, list[dict]] = {}
    for path in sorted(PAGES_ROOT.glob("*.md")):
        page = parse_page_file(path)
        if page is None:
            continue
        cluster = _cluster_for(meta=page["meta"])
        clusters.setdefault(cluster, []).append(page)

    lines = [
        "## By topic",
        "",
        "_Topic clusters maintained by the Consistency Agent; topics with the most pages first._",
        "",
    ]
    for cluster, pages in sorted(clusters.items(), key=lambda item: -len(item[1])):
        lines.append(f"### {cluster} ({len(pages)} page{'s' if len(pages) != 1 else ''})")
        lines.append("")
        for page in sorted(pages, key=lambda item: item["name"], reverse=True):
            title = str(page["meta"].get("title") or page["name"])
            lines.append(f"- [{title}](pages/{page['name']}) — {page['meta'].get('date') or ''}")
        lines.append("")

    contents = await _read_index()
    if "## By topic" in contents:
        head, _, _ = contents.partition("## By topic")
        updated = f"{head.rstrip()}\n\n" + "\n".join(lines).rstrip() + "\n"
    else:
        updated = f"{contents.rstrip()}\n\n" + "\n".join(lines).rstrip() + "\n"
    await _write_index(contents=updated)
    return len(clusters)


async def _check_agents_drift() -> list[str]:
    """Check AGENTS.md for the anchors the 2026-08-03 revalidation maintains.

    Returns:
        list[str]: The names of the drifted (missing) anchors.
    """
    if not AGENTS_PATH.is_file():
        return ["AGENTS.md missing"]
    text = AGENTS_PATH.read_text(encoding="utf-8")
    return [anchor for anchor in AGENTS_DRIFT_ANCHORS if anchor not in text]


async def revalidate_wiki_and_agents() -> dict:
    """Run the post-merge wiki/AGENTS.md revalidation sweep.

    Applies answered questions, merges near-duplicate pages, rebuilds the
    ``## By topic`` clusters and checks AGENTS.md drift anchors. Failures are
    logged and never raised.

    Returns:
        dict: Revision statistics keyed by pages merged, pages deleted,
            questions resolved, clusters rebuilt and drifted anchors.
    """
    stats = {
        "pages_merged": 0,
        "pages_deleted": 0,
        "questions_resolved": 0,
        "clusters_rebuilt": 0,
        "agents_drift": [],
    }
    try:
        stats["questions_resolved"] = await _answer_sweep()
        merged, deleted = await _dedup_pages()
        stats["pages_merged"] = merged
        stats["pages_deleted"] = deleted
        stats["clusters_rebuilt"] = await _regenerate_by_topic()
        stats["agents_drift"] = await _check_agents_drift()
    except Exception:  # noqa: BLE001
        logger.exception("Wiki revalidation failed")
    return stats


async def commit_revalidation(stats: dict) -> str | None:
    """Commit the revalidation changes to ``wiki/`` and ``AGENTS.md``.

    Args:
        stats: The revision statistics from ``revalidate_wiki_and_agents``.

    Returns:
        str | None: The commit SHA, or None when there was nothing to commit.
    """
    if not any(
        (
            stats.get("pages_merged"),
            stats.get("pages_deleted"),
            stats.get("questions_resolved"),
            stats.get("clusters_rebuilt"),
            stats.get("agents_drift"),
        )
    ):
        return None

    command = [str(GIT["path"]), "add", "wiki/", "AGENTS.md"]
    exit_code, _, stderr = await run_command(command=command, target_path=BASE_PATH, disable_stdio=True)
    if exit_code != 0:
        logger.warning(f"Failed to stage revalidation changes: {stderr.strip()}")
        return None

    diff_cmd = [str(GIT["path"]), "diff", "--staged", "--name-only"]
    _, staged, _ = await run_command(command=diff_cmd, target_path=BASE_PATH, disable_stdio=True)
    if not staged.strip():
        return None

    message = "Revalidate wiki and AGENTS.md (post-merge)"
    commit_cmd = [str(GIT["path"]), "commit", "-m", message, "--", "wiki/", "AGENTS.md"]
    exit_code, _, stderr = await run_command(command=commit_cmd, target_path=BASE_PATH, disable_stdio=True)
    if exit_code != 0:
        logger.warning(f"Failed to commit revalidation changes: {stderr.strip()}")
        return None

    rev_cmd = [str(GIT["path"]), "rev-parse", "HEAD"]
    _, sha, _ = await run_command(command=rev_cmd, target_path=BASE_PATH, disable_stdio=True)
    return sha.strip() or None


async def run_wiki_revalidation() -> dict:
    """RQ job entry point: revalidate the wiki and AGENTS.md after a merge.

    Errors are logged and never raised so a revalidation failure does not fail
    the job queue.

    Returns:
        dict: The revision statistics, including the commit SHA when committed.
    """
    stats = await revalidate_wiki_and_agents()
    try:
        stats["commit_sha"] = await commit_revalidation(stats=stats)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to commit wiki revalidation")
        stats["commit_sha"] = None
    logger.info("Wiki revalidation done: %s", stats)
    return stats
