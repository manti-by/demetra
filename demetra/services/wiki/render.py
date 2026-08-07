import os
from pathlib import Path

import aiofiles
import yaml

import demetra.services.wiki as service
from demetra.library.models import Context


def truncate(text: str, limit: int) -> str:
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


def dump_frontmatter(meta: dict) -> str:
    """Serialize the frontmatter mapping to a ``---``-delimited YAML block.

    Uses PyYAML ``safe_dump`` so every value is quoted correctly instead of the
    hand-rolled scalar quoting it replaces.

    Args:
        meta: The frontmatter mapping.

    Returns:
        str: The YAML block with a leading and trailing ``---``.
    """
    ordered = {
        "title": meta.get("title") or "",
        "date": meta.get("date") or "",
        "type": meta.get("type") or "",
        "status": meta.get("status") or "",
        "session_id": meta.get("session_id") or "",
        "services": meta.get("services") or [],
        "branch": meta.get("branch") or "-",
        "tickets": meta.get("tickets") or [],
        "tags": meta.get("tags") or [],
        "related": meta.get("related") or [],
    }
    block = yaml.safe_dump(data=ordered, default_flow_style=None, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{block}\n---"


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
    build_plan = service.truncate(text=build_plan, limit=service.WIKI_BUILD_PLAN_CAP)

    return "\n".join(
        [
            service.dump_frontmatter(meta),
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
            f"```text\n{facts.get('stat_text') or '- no stat'}\n```",
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


async def write_page(path: Path, body: str) -> None:
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


async def write_session_wiki_page(context: Context) -> None:
    """Write (or update) the wiki page for the current session.

    Failures are logged and never raised so a wiki error cannot fail the
    workflow.

    Args:
        context: The workflow context.
    """
    try:
        facts = service.collect_session_facts(context=context)
        identifier = facts["ticket_identifier"]
        title = facts["title"]

        existing = service.existing_page_for_ticket(ticket_identifier=identifier)
        filename = (
            existing.name
            if existing is not None
            else service.session_filename(ticket_identifier=identifier, title=title)
        )
        related: list[str] = []
        if existing is not None:
            try:
                existing_meta = service.parse_frontmatter(existing.read_text(encoding="utf-8"))
            except OSError:
                existing_meta = {}
            related = [item for item in (existing_meta.get("related") or []) if item != filename]

        diff = await service.git_diff_facts(target_path=context.worktree_path, env=context.project.environment)
        facts["files"] = diff["files"]
        facts["numstat"] = diff["numstat"]
        facts["changed_lines"] = diff["changed_lines"]
        facts["stat_text"] = diff["stat_text"]

        meta = {
            "title": f"{identifier}: {title}",
            "date": service.today(),
            "type": service.PAGE_TYPE,
            "status": service.PAGE_STATUS,
            "session_id": facts["session_id"] or "",
            "services": service.infer_services(facts["files"]),
            "branch": facts["branch"],
            "tickets": [identifier],
            "tags": service.infer_tags(linear_task=context.linear_task),
            "related": related,
            "linear_url": facts["url"] or "-",
        }

        polished_summary: dict | None = None
        if service.budget_exceeded(facts=facts):
            polished_summary = await service.summarize_session(
                ticket_text=context.linear_task.text,
                description=facts["description"],
                build_plan=facts["build_plan"] or "",
                diff_summary=facts["stat_text"] or "",
            )

        body = service.render_wiki_page(meta=meta, facts=facts, polished_summary=polished_summary)
        await service.write_page(path=service.PAGES_ROOT / filename, body=body)
        await service.patch_index(meta=meta, filename=filename)
        service.logger.info("Wrote wiki page %s for ticket %s", filename, identifier)
    except Exception:  # noqa: BLE001
        service.logger.exception("Failed to write wiki page for session; wiki failure is non-fatal")
