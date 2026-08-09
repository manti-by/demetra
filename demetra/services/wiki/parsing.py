import re
from pathlib import Path

import yaml

import demetra.services.wiki as service


def parse_page_file(path: Path) -> dict | None:
    """Parse a wiki page file into metadata and body content.

    Reads YAML frontmatter delimited by ``---`` lines; pages with invalid or
    non-mapping frontmatter are skipped with a warning. This is the shared
    parser used by both the read-side MCP tools and the write-side service.

    Args:
        path: Path of the ``.md`` page file.

    Returns:
        dict | None: A mapping with ``name``, ``meta`` and ``body`` keys, or
            None when the file cannot be read or its frontmatter parsed.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        service.logger.warning(f"Skipping unreadable page: {path.name}")
        return None
    meta: dict = {}
    body = text
    match = service.FRONTMATTER_RE.match(text)
    if match:
        block = service.BARE_DASH_RE.sub(r'\1"-"', match.group(1))
        try:
            parsed = yaml.safe_load(block)
        except yaml.YAMLError:
            service.logger.warning(f"Skipping page with invalid frontmatter: {path.name}")
            return None
        if parsed is not None and not isinstance(parsed, dict):
            service.logger.warning(f"Skipping page with non-mapping frontmatter: {path.name}")
            return None
        meta = parsed or {}
        body = text[match.end() :]
    return {"name": path.name, "meta": meta, "body": body}


def parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter delimited by ``---`` lines.

    Tolerant mirror of the read side used for quick ticket lookups.

    Args:
        text: The full page text.

    Returns:
        dict: The parsed frontmatter mapping, or an empty dict when absent.
    """
    match = service.FRONTMATTER_RE.match(text)
    if not match:
        return {}
    block = service.BARE_DASH_RE.sub(r'\1"-"', match.group(1))
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def existing_page_for_ticket(ticket_identifier: str) -> Path | None:
    """Find an existing wiki page for a ticket, if any.

    Args:
        ticket_identifier: The Linear ticket identifier, e.g. ``MNT-147``.

    Returns:
        Path | None: The existing page file, or None when no page references the
            ticket.
    """
    if not service.PAGES_ROOT.is_dir():
        return None
    for path in sorted(service.PAGES_ROOT.glob("*.md")):
        try:
            meta = service.parse_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if ticket_identifier in (meta.get("tickets") or []):
            return path
    return None


def page_date(path: Path) -> str:
    """Return the frontmatter ``date`` of a page, defaulting to its filename date.

    Args:
        path: The page path.

    Returns:
        str: The page date in ``YYYY-MM-DD`` form.
    """
    try:
        meta = service.parse_frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("date"):
            return str(meta["date"])
    except (OSError, yaml.YAMLError):
        pass
    match = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
    return match.group(1) if match else "0000-00-00"
