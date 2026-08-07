from datetime import UTC, datetime
from pathlib import Path

from slugify import slugify

import demetra.services.wiki as service
from demetra.library.models import LinearTask


def today() -> str:
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
    return f"{service.today()}-{slugify(f'{ticket_identifier.strip()}-{title.strip()}')}.md"


def infer_services(changed_files: list[str]) -> list[str]:
    """Infer the affected ``services`` from changed file paths.

    Args:
        changed_files: The list of changed file paths.

    Returns:
        list[str]: The de-duplicated, ordered service names.
    """
    services: list[str] = []
    for path in sorted(changed_files):
        name = None
        if path.startswith("demetra/services/") and path.endswith(".py"):
            name = path.removeprefix("demetra/services/").removesuffix(".py")
        elif path == "demetra/settings.py":
            name = "settings"
        elif path.startswith("demetra") and "/" in path:
            name = path.split("/")[1]
        else:
            name = Path(path).stem
        if name and name not in services:
            services.append(name)
    return services


def infer_tags(linear_task: LinearTask) -> list[str]:
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
