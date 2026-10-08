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


def render_page(meta: dict, body: str) -> str:
    """Assemble the complete page from the frontmatter and the LLM-authored body.

    The frontmatter and the H1 stay deterministic so the page remains
    machine-queryable and its title always matches the ``title`` field; the LLM
    authors everything from the first ``##`` heading down.

    Args:
        meta: The frontmatter mapping.
        body: The page body Markdown, starting at the first ``##`` heading.

    Returns:
        str: The complete page Markdown.
    """
    return f"{service.dump_frontmatter(meta)}\n\n# {meta['title']}\n\n{body.strip()}\n"


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


async def write_session_wiki_page(context: Context, wiki_root: Path | None = None) -> None:
    """Write (or update) the wiki page for the current session.

    The page is written under ``pages/`` and the matching ``INDEX.md`` is
    patched inside ``wiki_root``. When ``wiki_root`` is omitted the service
    ``PAGES_ROOT`` / ``INDEX_PATH`` are used; pass the worktree's ``wiki``
    directory so the freshly-written page is picked up by the next ``git add``
    and included in the commit.

    Failures raise ``WikiError`` so the caller can decide how to handle them
    (e.g. move the ticket to ``Awaiting Input``).

    Args:
        context: The workflow context.
        wiki_root: Optional wiki root directory; defaults to the service
            ``PAGES_ROOT`` / ``INDEX_PATH``.

    Raises:
        WikiError: When the wiki page or index cannot be written.
    """
    if wiki_root is not None:
        pages_root = wiki_root / "pages"
        index_path = wiki_root / "INDEX.md"
    else:
        pages_root = service.PAGES_ROOT
        index_path = service.INDEX_PATH
    identifier = "unknown"
    try:
        facts = service.collect_session_facts(context=context)
        identifier = facts["ticket_identifier"]
        title = facts["title"]

        existing = service.existing_page_for_ticket(ticket_identifier=identifier, pages_root=pages_root)
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

        diff = await service.git_diff_facts(target_path=context.worktree_path, environment=context.environment)
        facts["files"] = diff["files"]
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
        }

        page_body = await service.compose_wiki_page(
            title=meta["title"],
            page_type=meta["type"],
            ticket_text=context.linear_task.text,
            description=facts["description"],
            build_plan=facts["build_plan"],
            diff_summary=facts["stat_text"],
            log_tail=facts["log_tail"],
            linear_url=facts["url"] or "-",
            related=related,
            environment=context.environment,
        )

        await service.write_page(path=pages_root / filename, body=service.render_page(meta=meta, body=page_body))
        await service.patch_index(meta=meta, filename=filename, index_path=index_path)
        service.logger.info("Wrote wiki page %s for ticket %s", filename, identifier)
    except Exception as e:  # noqa: BLE001
        service.logger.exception("Failed to write wiki page for session")
        raise service.WikiError(f"Failed to write wiki page for {identifier}: {e}") from e
