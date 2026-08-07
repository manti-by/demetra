import os

import aiofiles

import demetra.services.wiki as service


def index_entry(meta: dict, filename: str) -> str:
    """Build the INDEX ``## Pages`` line for a page.

    Args:
        meta: The page frontmatter mapping.
        filename: The page file name.

    Returns:
        str: A bullet line like ``- [Title](pages/file.md) — summary``.
    """
    summary = f"Implementation of {meta['title']} ({meta['date']})"
    return f"- [{meta['title']}](pages/{filename}) — {summary}"


async def read_index() -> str:
    """Read the wiki INDEX file.

    Returns:
        str: The current ``wiki/INDEX.md`` contents, or an empty string.
    """
    if not service.INDEX_PATH.is_file():
        return ""
    async with aiofiles.open(service.INDEX_PATH, encoding="utf-8") as handle:
        return await handle.read()


async def write_index(contents: str) -> None:
    """Atomically write the wiki INDEX file.

    Args:
        contents: The new ``wiki/INDEX.md`` contents.
    """
    service.INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = service.INDEX_PATH.with_suffix(f"{service.INDEX_PATH.suffix}.tmp")
    async with aiofiles.open(tmp, "w", encoding="utf-8") as handle:
        await handle.write(contents)
    os.replace(tmp, service.INDEX_PATH)


def insert_pages_entry(contents: str, entry: str) -> str:
    """Insert a new entry at the top of the ``## Pages`` section.

    The ``## Pages`` section is newest-first; the new page is inserted
    immediately after the section header. Idempotent by page link target: a line
    already linking ``pages/{filename}`` is replaced with the new entry.

    Args:
        contents: The current INDEX contents.
        entry: The new bullet line.

    Returns:
        str: The updated INDEX contents.
    """
    page_match = service.PAGE_LINK_RE.search(entry)
    page_link = f"](pages/{page_match.group(1)})" if page_match else entry
    lines = contents.splitlines()
    in_pages = False
    insert_at = None
    modified = False
    for index, line in enumerate(lines):
        if line.strip() == "## Pages":
            in_pages = True
            insert_at = index + 1
            continue
        if not in_pages:
            continue
        if line.strip().startswith("## "):
            if insert_at is not None:
                lines.insert(insert_at, entry)
                modified = True
            break
        if page_link in line:
            if line != entry:
                lines[index] = entry
                modified = True
            break
        if line.lstrip().startswith("- ["):
            lines.insert(index, entry)
            modified = True
            break
        if insert_at is not None:
            insert_at = index + 1
    else:
        if in_pages and insert_at is not None:
            lines.insert(insert_at, entry)
            modified = True
        else:
            lines.extend(["", "## Pages", "", entry])
            modified = True
    return "\n".join(lines) if modified else contents


async def prune_index_pages(deleted_names: list[str]) -> None:
    """Remove ``## Pages`` bullets that link to the given page files.

    Args:
        deleted_names: The page file names that were removed.
    """
    contents = await service.read_index()
    if not contents:
        return
    lines = contents.splitlines()
    in_pages = False
    pruned = False
    kept: list[str] = []
    for line in lines:
        if line.strip() == "## Pages":
            in_pages = True
            kept.append(line)
            continue
        if in_pages and line.strip().startswith("## "):
            in_pages = False
            kept.append(line)
            continue
        if in_pages and any(f"](pages/{name})" in line for name in deleted_names):
            pruned = True
            continue
        kept.append(line)
    if pruned:
        await service.write_index(contents="\n".join(kept))


def find_topic_cluster(contents: str, meta: dict) -> str:
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


def insert_cluster_entry(contents: str, cluster_header: str, entry: str) -> str:
    """Append a page bullet under a ``## By topic`` cluster.

    Idempotent by page link target: a line already linking the same page file
    is left untouched. Headers are matched on their stripped form, the blank
    separator before the next cluster is preserved, and appending at the end
    keeps a trailing blank line.

    Args:
        contents: The current INDEX contents.
        cluster_header: The target cluster header line.
        entry: The bullet line to append.

    Returns:
        str: The updated INDEX contents.
    """
    page_match = service.PAGE_LINK_RE.search(entry)
    page_link = f"](pages/{page_match.group(1)})" if page_match else entry
    target = cluster_header.strip().split(" (", 1)[0]
    lines = contents.splitlines()
    in_cluster = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("### ") and stripped.split(" (", 1)[0] == target:
            in_cluster = True
            continue
        if not in_cluster:
            continue
        if page_link in line:
            break
        if stripped.startswith("### "):
            if lines[index - 1].strip() == "":
                lines.insert(index - 1, entry)
            else:
                lines.insert(index, entry)
            break
        if index == len(lines) - 1:
            lines.append(entry)
            lines.append("")
            break
    else:
        return contents
    return "\n".join(lines)


async def patch_index(meta: dict, filename: str) -> None:
    """Update ``INDEX.md`` with a new page entry.

    Inserts the entry into ``## Pages`` (newest-first) and appends a bullet
    under the best-matching ``## By topic`` cluster. When the index has no
    ``## By topic`` section yet, it is regenerated from the page catalog first
    so the cluster insert has a target.

    Args:
        meta: The page frontmatter mapping.
        filename: The page file name.
    """
    contents = await service.read_index()
    pages_entry = service.index_entry(meta=meta, filename=filename)
    updated = service.insert_pages_entry(contents=contents, entry=pages_entry)
    if "## By topic" not in updated:
        await service.write_index(contents=updated)
        await service.regenerate_by_topic()
        updated = await service.read_index()
    cluster = service.find_topic_cluster(contents=updated, meta=meta)
    cluster_entry = f"- [{meta['title']}](pages/{filename}) — {meta['date']}"
    updated = service.insert_cluster_entry(contents=updated, cluster_header=cluster, entry=cluster_entry)
    await service.write_index(contents=updated)


def cluster_for(meta: dict) -> str:
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
    for cluster, keywords in service.TOPIC_KEYWORDS.items():
        score = sum(haystack.count(keyword) for keyword in keywords)
        if score > best[1]:
            best = (cluster, score)
    return best[0]


async def regenerate_by_topic() -> int:
    """Rebuild the ``## By topic`` section of INDEX.md from page frontmatter.

    Returns:
        int: The number of topic clusters written.
    """
    if not service.PAGES_ROOT.is_dir():
        return 0
    clusters: dict[str, list[dict]] = {}
    for path in sorted(service.PAGES_ROOT.glob("*.md")):
        page = service.parse_page_file(path=path)
        if page is None:
            continue
        cluster = service.cluster_for(meta=page["meta"])
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

    contents = await service.read_index()
    marker = "## By topic"
    if marker in contents:
        head, _, tail = contents.partition(marker)
        tail_lines = tail.splitlines()
        next_index = next(
            (index for index, line in enumerate(tail_lines[1:], start=1) if line.startswith("## ")),
            None,
        )
        if next_index is None:
            updated = f"{head.rstrip()}\n\n" + "\n".join(lines).rstrip() + "\n"
        else:
            trailing = "\n".join(tail_lines[next_index:])
            updated = f"{head.rstrip()}\n\n" + "\n".join(lines).rstrip() + "\n\n" + trailing.rstrip() + "\n"
    else:
        updated = f"{contents.rstrip()}\n\n" + "\n".join(lines).rstrip() + "\n"
    await service.write_index(contents=updated)
    return len(clusters)
