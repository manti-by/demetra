import argparse
import asyncio
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

import yaml

import demetra.services.wiki as service
from demetra.library.exceptions import WikiError
from demetra.library.models import SessionEnvironment
from demetra.services.runtime.tui import print_message


OKF_STATUSES: tuple[str, ...] = ("draft", "stable", "deprecated")
OKF_GENERATED_BY = "demetra"
OKF_STATUS_MAP: dict[str, str] = {
    "resolved": "stable",
    "reference": "stable",
    "open": "draft",
    "in-progress": "draft",
}
OKF_DESCRIPTION_INPUT_CAP = 20_000
OKF_DEFAULT_CONCURRENCY = 4

OKF_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
OKF_DATETIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\Z")
WIKILINK_RE = re.compile(r"\[\[([^\[\]\n]+)\]\]")
INLINE_CODE_RE = re.compile(r"(`[^`\n]*`)")
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
RESERVED_NAMES = ("index.md", "log.md")

DescriptionFn = Callable[..., Awaitable[str]]


def okf_datetime_text(value: object) -> str:
    """Return an ISO 8601 datetime string from a string or a parsed datetime.

    Args:
        value: A frontmatter value holding a datetime.

    Returns:
        str: The datetime in ISO 8601 form, or an empty string.
    """
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return str(value or "")


def okf_date(value: object) -> str:
    """Extract a ``YYYY-MM-DD`` date from a frontmatter value.

    Args:
        value: A date, datetime or free-form string.

    Returns:
        str: The extracted date, or an empty string.
    """
    match = OKF_DATE_RE.search(okf_datetime_text(value))
    return match.group(1) if match else ""


def okf_page_date(meta: dict, path: Path | None = None) -> str:
    """Return the effective page date from ``generated.at`` or the fallback.

    Args:
        meta: The page frontmatter mapping.
        path: Optional page path supplying a date-prefixed filename fallback.

    Returns:
        str: The page date in ``YYYY-MM-DD`` form.
    """
    generated = meta.get("generated")
    if isinstance(generated, dict):
        date = okf_date(generated.get("at"))
        if date:
            return date
    date = okf_date(meta.get("date"))
    if date:
        return date
    fallback = okf_date(path.name) if path is not None else ""
    return fallback or "0000-00-00"


def generated_at(value: object = "", path: Path | None = None) -> dict[str, str]:
    """Build the OKF ``generated`` mapping from a date or datetime.

    Args:
        value: The legacy ``date`` value or an ISO 8601 datetime.
        path: Optional page path supplying a date-prefixed filename fallback.

    Returns:
        dict[str, str]: The ``by`` / ``at`` actor mapping.
    """
    text = okf_datetime_text(value)
    if OKF_DATETIME_RE.fullmatch(text):
        return {"by": OKF_GENERATED_BY, "at": text}
    date = okf_date(text) or (okf_date(path.name) if path is not None else "") or service.today()
    return {"by": OKF_GENERATED_BY, "at": f"{date}T00:00:00Z"}


def _roots(wiki_root: Path | None = None) -> tuple[Path, Path]:
    root = wiki_root if wiki_root is not None else service.WIKI_ROOT
    return root / "pages", root / "archive"


def okf_status(meta: dict, path: Path | None = None, *, wiki_root: Path | None = None) -> str:
    """Map a legacy frontmatter status onto the OKF lifecycle values.

    Args:
        meta: The page frontmatter mapping.
        path: Optional page path; archived pages are always deprecated.
        wiki_root: Optional wiki root used to locate the archive directory.

    Returns:
        str: One of ``draft``, ``stable`` or ``deprecated``.
    """
    archive_root = _roots(wiki_root=wiki_root)[1]
    if path is not None:
        try:
            path.resolve().relative_to(archive_root.resolve())
        except ValueError:
            pass
        else:
            return "deprecated"
    return OKF_STATUS_MAP.get(str(meta.get("status") or "").casefold(), "stable")


def resolve_wikilink(stem: str, *, wiki_root: Path | None = None) -> str:
    """Resolve a page stem to an absolute bundle-relative OKF link.

    Args:
        stem: The wikilink target, with or without a ``.md`` suffix.
        wiki_root: Optional wiki root used to locate pages and the archive.

    Returns:
        str: A link into ``/pages/`` or ``/archive/``.
    """
    _, archive_root = _roots(wiki_root=wiki_root)
    name = stem if stem.endswith(".md") else f"{stem}.md"
    if (archive_root / name).is_file():
        return f"/archive/{name}"
    return f"/pages/{name}"


def convert_wikilinks(text: str, *, wiki_root: Path | None = None) -> tuple[str, list[str]]:
    """Convert ``[[stem]]`` links to standard OKF markdown links.

    Fenced code blocks and inline code spans are left untouched, so source
    examples that mention wikilink syntax remain verbatim.

    Args:
        text: The markdown text to convert.
        wiki_root: Optional wiki root used to resolve target directories.

    Returns:
        tuple[str, list[str]]: The converted text and unresolved target stems.
    """
    pages_root, archive_root = _roots(wiki_root=wiki_root)
    unresolved: list[str] = []
    fence: str | None = None
    lines: list[str] = []

    def replace(match: re.Match[str]) -> str:
        stem = match.group(1).strip()
        if not stem or any(char in stem for char in "|#"):
            return match.group(0)
        name = stem if stem.endswith(".md") else f"{stem}.md"
        if not (pages_root / name).is_file() and not (archive_root / name).is_file():
            unresolved.append(stem)
        return f"[{stem}]({resolve_wikilink(stem, wiki_root=wiki_root)})"

    for line in text.splitlines(keepends=True):
        fence_match = FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            lines.append(line)
            continue
        if fence is not None:
            lines.append(line)
            continue
        segments = INLINE_CODE_RE.split(line)
        for index in range(0, len(segments), 2):
            segments[index] = WIKILINK_RE.sub(replace, segments[index])
        lines.append("".join(segments))
    return "".join(lines), unresolved


def parse_okf_page(text: str) -> dict | None:
    """Parse frontmatter with plain YAML, as an OKF consumer would.

    Args:
        text: The complete page text.

    Returns:
        dict | None: The parsed mapping, or None when frontmatter is absent or
            not a mapping.
    """
    match = service.FRONTMATTER_RE.match(text)
    if not match:
        return None
    try:
        parsed = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def validate_page(text: str, *, path: Path | None = None, require_okf: bool = True) -> list[str]:
    """Check a page against OKF conformance and the local page conventions.

    Args:
        text: The complete page text.
        path: Optional path used to check reserved filenames.
        require_okf: When False, only check OKF §11 conformance.

    Returns:
        list[str]: The violations found, empty for a conformant page.
    """
    issues: list[str] = []
    if path is not None and path.name.casefold() in RESERVED_NAMES:
        issues.append("reserved filename inside bundle")
    parsed = parse_okf_page(text)
    if parsed is None:
        return [*issues, "missing, invalid or non-mapping YAML frontmatter"]
    if not str(parsed.get("type") or "").strip():
        issues.append("missing or empty type")
    if not require_okf:
        return issues
    if parsed.get("status") not in OKF_STATUSES:
        issues.append(f"invalid status: {parsed.get('status')!r}")
    generated = parsed.get("generated")
    at_text = okf_datetime_text(generated.get("at")) if isinstance(generated, dict) else ""
    if not isinstance(generated, dict) or not str(generated.get("by") or "").strip() or not OKF_DATETIME_RE.fullmatch(at_text):
        issues.append("missing or invalid generated by/at")
    if not str(parsed.get("description") or "").strip():
        issues.append("missing or empty description")
    match = service.FRONTMATTER_RE.match(text)
    body = text[match.end() :] if match else text
    converted, _ = convert_wikilinks(body)
    if len(WIKILINK_RE.findall(body)) > len(WIKILINK_RE.findall(converted)):
        issues.append("unconverted wikilinks in body")
    return issues


def strip_leading_h1(body: str) -> str:
    """Drop the page's existing H1 so the renderer's title stays unique.

    Args:
        body: The page body following the frontmatter block.

    Returns:
        str: The body without its first H1 line.
    """
    lines = body.lstrip("\n").splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).lstrip("\n")


def migrate_page(*, text: str, description: str, path: Path, wiki_root: Path | None = None) -> str:
    """Rewrite one legacy page into OKF form.

    Args:
        text: The complete legacy page text.
        description: The LLM-authored one-line description.
        path: The page path, used for status and filename date fallback.
        wiki_root: Optional wiki root used to resolve links and the archive.

    Returns:
        str: The complete OKF page text.
    """
    meta = service.parse_frontmatter(text)
    match = service.FRONTMATTER_RE.match(text)
    body = text[match.end() :] if match else text
    new_meta = {
        "title": meta.get("title") or "",
        "generated": generated_at(meta.get("date") or "", path),
        "description": description,
        "type": meta.get("type") or "",
        "status": okf_status(meta, path, wiki_root=wiki_root),
        "session_id": meta.get("session_id") or "-",
        "services": meta.get("services") or [],
        "branch": meta.get("branch") or "-",
        "tickets": meta.get("tickets") or [],
        "tags": meta.get("tags") or [],
        "related": meta.get("related") or [],
    }
    converted, _ = convert_wikilinks(strip_leading_h1(body), wiki_root=wiki_root)
    return service.render_page(meta=new_meta, body=converted)


def validate_bundle(wiki_root: Path | None = None) -> dict:
    """Validate every Markdown file in the OKF bundle.

    Args:
        wiki_root: Optional wiki root; defaults to the service root.

    Returns:
        dict: File count, wikilink count and violations keyed by relative path.
    """
    root = wiki_root if wiki_root is not None else service.WIKI_ROOT
    violations: dict[str, list[str]] = {}
    files = 0
    wikilinks = 0
    for folder in ("pages", "archive"):
        directory = root / folder
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            files += 1
            text = path.read_text(encoding="utf-8")
            wikilinks += len(WIKILINK_RE.findall(text)) - len(WIKILINK_RE.findall(convert_wikilinks(text)[0]))
            issues = validate_page(text, path=path)
            if issues:
                violations[str(path.relative_to(root))] = issues
    return {"files": files, "wikilinks": wikilinks, "violations": violations}


async def migrate_bundle(
    *,
    wiki_root: Path | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    concurrency: int = OKF_DEFAULT_CONCURRENCY,
    description_fn: DescriptionFn | None = None,
    environment: SessionEnvironment | None = None,
) -> dict:
    """Validate and migrate the OKF bundle in one pass.

    Pages already conformant are skipped, so a failed run can be retried.

    Args:
        wiki_root: Optional wiki root; defaults to the service root.
        dry_run: When True, generate descriptions but write nothing.
        limit: Optional cap on the number of pages processed.
        concurrency: Maximum number of concurrent description calls.
        description_fn: Optional description generator for tests or offline runs.
        environment: Optional resolved environment for the LLM calls.

    Returns:
        dict: Before/after validation reports and migration counters.
    """
    root = wiki_root if wiki_root is not None else service.WIKI_ROOT
    before = validate_bundle(wiki_root=root)
    generate = description_fn if description_fn is not None else service.compose_wiki_description
    paths = [path for folder in ("pages", "archive") for path in sorted((root / folder).glob("*.md"))]
    if limit is not None:
        paths = paths[:limit]

    migrated: list[str] = []
    skipped: list[str] = []
    failed: dict[str, str] = {}
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def one(path: Path) -> None:
        async with semaphore:
            try:
                text = path.read_text(encoding="utf-8")
                if not validate_page(text, path=path):
                    skipped.append(path.name)
                    return
                match = service.FRONTMATTER_RE.match(text)
                body = text[match.end() :] if match else text
                description = await generate(content=body[:OKF_DESCRIPTION_INPUT_CAP], environment=environment)
                if not dry_run:
                    rendered = migrate_page(text=text, description=description, path=path, wiki_root=root)
                    await service.write_page(path=path, body=rendered)
                migrated.append(path.name)
            except (OSError, WikiError, yaml.YAMLError, ValueError) as error:
                failed[path.name] = str(error)

    await asyncio.gather(*(one(path) for path in paths))
    after = {"files": before["files"], "wikilinks": 0, "violations": {}} if dry_run else validate_bundle(wiki_root=root)
    return {"before": before, "after": after, "migrated": migrated, "skipped": skipped, "failed": failed}


def okf_cli(*, dry_run: bool = False, limit: int | None = None, concurrency: int = OKF_DEFAULT_CONCURRENCY) -> int:
    """Report OKF validation and migration results as a process exit code.

    Args:
        dry_run: When True, report violations without writing pages.
        limit: Optional cap on the number of pages processed.
        concurrency: Maximum number of concurrent description calls.

    Returns:
        int: 0 on a clean run, 1 when pages fail or remain invalid.
    """
    report = asyncio.run(migrate_bundle(dry_run=dry_run, limit=limit, concurrency=concurrency))
    before = report["before"]
    after = report["after"]
    print_message(
        f"OKF validation: {before['files']} files, {before['wikilinks']} wikilinks, "
        f"{len(before['violations'])} invalid pages",
        style="heading",
    )
    prefix = "(dry-run) " if dry_run else ""
    print_message(
        f"{prefix}migrated {len(report['migrated'])} pages, skipped {len(report['skipped'])}, "
        f"failed {len(report['failed'])}",
        style="result",
    )
    for name, issues in after["violations"].items():
        print_message(f"Invalid {name}: {'; '.join(issues)}", style="error")
    for name, error in report["failed"].items():
        print_message(f"Failed {name}: {error}", style="error")
    return 1 if report["failed"] or after["violations"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="demetra-okf", description="Validate and migrate the wiki OKF bundle")
    parser.add_argument("--dry-run", action="store_true", help="Report violations without writing pages")
    parser.add_argument("--limit", type=int, default=None, help="Process at most this many pages")
    parser.add_argument("--concurrency", type=int, default=OKF_DEFAULT_CONCURRENCY, help="Concurrent LLM calls")
    args = parser.parse_args()
    raise SystemExit(okf_cli(dry_run=args.dry_run, limit=args.limit, concurrency=args.concurrency))
