import logging
from pathlib import Path
from typing import Any

from mcp.types import TextContent, Tool

from demetra.services.wiki import PAGES_ROOT, parse_page_file
from demetra.settings import SEARCH
from demetra.tools.result import ToolResult
from demetra.tools.search import (
    CorpusStats,
    Field,
    FieldCounts,
    build_stats,
    count_field,
    line_hits,
    score_document,
    tokenize,
)


logger = logging.getLogger(__name__)

WIKI_FIELDS = (
    Field(weight=SEARCH["wiki_title_boost"], length_norm=SEARCH["wiki_title_length_norm"]),
    Field(weight=SEARCH["wiki_metadata_boost"], length_norm=SEARCH["wiki_metadata_length_norm"]),
    Field(weight=SEARCH["wiki_body_boost"], length_norm=SEARCH["wiki_body_length_norm"]),
)

_cached_fingerprint: tuple[tuple[str, int, int], ...] | None = None
_cached_pages: list[dict[str, Any]] = []
_cached_documents: list[tuple[FieldCounts, ...]] = []
_cached_stats: CorpusStats | None = None
_cached_pages_root: Path | None = None


def _page_fields(page: dict[str, Any]) -> tuple[FieldCounts, ...]:
    """Count searchable tokens in a page's title, metadata and body zones.

    Args:
        page: The parsed wiki page.

    Returns:
        tuple[FieldCounts, ...]: Field counts aligned to ``WIKI_FIELDS``.
    """
    return (
        count_field(text=str(page["meta"].get("title") or "")),
        count_field(text=_metadata_text(meta=page["meta"])),
        count_field(text=page["body"]),
    )


def _fingerprint(paths: list[Path], pages_root: Path) -> tuple[tuple[str, int, int], ...]:
    """Build a change fingerprint for the wiki page files.

    Args:
        paths: Page files to fingerprint.
        pages_root: Root directory used to create relative paths.

    Returns:
        tuple[tuple[str, int, int], ...]: Relative paths, modification times,
            and sizes for cache invalidation.
    """
    entries: list[tuple[str, int, int]] = []
    for path in paths:
        try:
            metadata = path.stat()
        except OSError:
            continue
        entries.append((str(path.relative_to(pages_root)), metadata.st_mtime_ns, metadata.st_size))
    return tuple(entries)


def _load_pages(pages_root: Path) -> list[dict[str, Any]]:
    """Load all valid wiki pages from a directory, sorted by name.

    Parsed pages and their BM25 field counts are cached and rebuilt only when a
    page file is added, removed, archived or otherwise changes its modification
    time or size, so repeated searches skip re-reading and re-tokenizing every
    page in the corpus.

    Args:
        pages_root: Directory containing ``*.md`` wiki page files.

    Returns:
        list[dict[str, Any]]: The parsed pages in sorted filename order.
    """
    global _cached_fingerprint, _cached_pages, _cached_documents, _cached_stats, _cached_pages_root

    paths = sorted(pages_root.glob("*.md")) if pages_root.is_dir() else []
    fingerprint = _fingerprint(paths=paths, pages_root=pages_root)
    if pages_root == _cached_pages_root and fingerprint == _cached_fingerprint:
        return _cached_pages

    pages = [page for path in paths if (page := parse_page_file(path=path)) is not None]
    documents = [_page_fields(page=page) for page in pages]
    _cached_fingerprint = fingerprint
    _cached_pages = pages
    _cached_documents = documents
    _cached_stats = build_stats(fields=WIKI_FIELDS, documents=documents)
    _cached_pages_root = pages_root
    return pages


def _resolve_page(pages_root: Path, name: str) -> Path | None:
    """Resolve a page name to a file path confined to the pages directory.

    Appends the ``.md`` suffix when needed and rejects any path that escapes
    the pages root.

    Args:
        pages_root: Directory containing the wiki page files.
        name: Page file name, with or without the ``.md`` suffix.

    Returns:
        Path | None: The resolved file path if the page exists, otherwise
            None.
    """
    slug = name.strip().removeprefix("pages/")
    if not slug.endswith(".md"):
        slug = f"{slug}.md"
    target = (pages_root / slug).resolve()
    try:
        target.relative_to(pages_root)
    except ValueError:
        return None
    return target if target.is_file() else None


def _tokenize(query: str) -> list[str]:
    """Split a query into lowercase terms, dropping stop words and short terms.

    Args:
        query: The raw search query.

    Returns:
        list[str]: The meaningful search terms.
    """
    return tokenize(query=query)


def _metadata_text(meta: dict[str, Any]) -> str:
    """Flatten searchable frontmatter fields into a lowercase string.

    Combines tags, services, tickets and type values for scoring.

    Args:
        meta: The page frontmatter mapping.

    Returns:
        str: A space-joined lowercase string of metadata values.
    """
    parts = []
    for key in ("tags", "services", "tickets", "type"):
        value = meta.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))
    return " ".join(parts).lower()


def _extract_snippets(body: str, terms: list[str]) -> list[str]:
    """Pick the most relevant line snippets from a page body.

    Lines are scored by how many distinct query terms they contain as whole
    tokens, capped at the configured maximum, and returned in line-number order
    with a length cap per snippet.

    Args:
        body: The page body text.
        terms: The search terms to match against lines.

    Returns:
        list[str]: Snippet lines prefixed with their line number.
    """
    scored: list[tuple[int, int, str]] = []
    for lineno, line in enumerate(body.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        hits = line_hits(line=stripped, terms=terms)
        if hits:
            scored.append((-hits, lineno, stripped))
    scored.sort(key=lambda item: item[0])
    top = scored[: SEARCH["max_snippets"]]
    top.sort(key=lambda item: item[1])
    return [f"L{lineno}: {text[: SEARCH['snippet_length']]}" for _, lineno, text in top]


def _search_pages(pages_root: Path, query: str, limit: int) -> list[dict[str, Any]]:
    """Search the wiki pages and return the top matches for a query.

    Pages are ranked with BM25F across the title, metadata and body fields, so
    rare terms outweigh common ones and a long page cannot win on bulk alone.

    Args:
        pages_root: Directory containing the wiki page files.
        query: The raw search query.
        limit: Maximum number of results to return.

    Returns:
        list[dict[str, Any]]: Ranked results, each holding ``page``, ``score``
            and ``terms``, or an empty list when the query has no terms.
    """
    terms = _tokenize(query)
    if not terms:
        return []
    pages = _load_pages(pages_root)
    stats = _cached_stats
    if stats is None:
        return []
    results: list[dict[str, Any]] = []
    for page, document in zip(pages, _cached_documents, strict=True):
        score = score_document(fields=WIKI_FIELDS, document=document, stats=stats, terms=terms)
        if score > 0:
            results.append({"page": page, "score": score, "terms": terms})
    results.sort(key=lambda result: (-result["score"], result["page"]["name"]))
    return results[:limit]


def _summarize_meta(meta: dict[str, Any]) -> str:
    """Render the key frontmatter fields of a page as a readable summary.

    Args:
        meta: The page frontmatter mapping.

    Returns:
        str: A comma-joined summary of type, date, status and list fields.
    """
    parts = [
        f"type: {meta.get('type') or '-'}",
        f"date: {meta.get('date') or '-'}",
        f"status: {meta.get('status') or '-'}",
    ]
    for key in ("services", "tags", "tickets"):
        value = meta.get(key)
        if isinstance(value, list) and value:
            parts.append(f"{key}: {', '.join(str(item) for item in value)}")
        elif value:
            parts.append(f"{key}: {value}")
    return ", ".join(parts)


def _page_title(page: dict[str, Any]) -> str:
    """Return the display title of a page, falling back to its filename.

    Args:
        page: The parsed wiki page.

    Returns:
        str: The frontmatter title, or the page file name when absent.
    """
    return str(page["meta"].get("title") or page["name"])


AVAILABLE_TOOLS = [
    Tool(
        name="wiki_search",
        description=(
            "Search the project wiki of past debugging sessions, investigations, code reviews, and "
            "implementation notes. Consult this BEFORE answering questions about why something works "
            "the way it does, past decisions, or prior incidents. Returns ranked page names with "
            "snippets; fetch a full page with wiki_get_page."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (keywords or a question)"},
                "limit": {
                    "type": "integer",
                    "description": (f"Max results (default {SEARCH['default_limit']}, max {SEARCH['max_results']})"),
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="wiki_get_page",
        description=(
            "Get the full Markdown content of a single wiki page by its file name, as returned by "
            "wiki_search or wiki_list_pages."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Page file name, e.g. 2026-08-03-fix-mcp-server-2.0-api.md",
                },
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="wiki_list_pages",
        description=(
            "List all project wiki pages with their metadata (title, type, date, status, services, "
            "tags, tickets) without reading page bodies."
        ),
        input_schema={
            "type": "object",
            "properties": {},
        },
    ),
]


async def list_tools() -> list[Tool]:
    """Return the wiki MCP tool definitions.

    Returns:
        list[Tool]: The static list of available wiki tools.
    """
    return AVAILABLE_TOOLS


def _format_search_results(results: list[dict[str, Any]]) -> str:
    """Format ranked search results into a readable text block.

    Args:
        results: The ranked search results from ``_search_pages``.

    Returns:
        str: A numbered, snippet-bearing summary of each result.
    """
    blocks = []
    for position, result in enumerate(results, start=1):
        page = result["page"]
        snippets = _extract_snippets(page["body"], result["terms"])
        snippet_lines = "\n".join(f"   > {snippet}" for snippet in snippets)
        blocks.append(
            f"{position}. {page['name']} (score {result['score']:.3f})\n"
            f"   {_page_title(page)} — {_summarize_meta(page['meta'])}\n"
            f"{snippet_lines}"
        )
    return "\n\n".join(blocks)


async def call_tool(name: str, arguments: dict | None) -> ToolResult:
    """Dispatch a wiki MCP tool call by name.

    Supports listing, searching and fetching wiki pages, wrapping both
    results and errors into a ToolResult.

    Args:
        name: The name of the wiki tool to invoke.
        arguments: Optional tool arguments as a mapping.

    Returns:
        ToolResult: The tool output, or an error result on failure.
    """
    args = arguments or {}
    try:
        if not PAGES_ROOT.is_dir():
            return ToolResult(
                content=[TextContent(type="text", text="Wiki pages directory not found")],
                is_error=True,
            )

        if name == "wiki_list_pages":
            pages = _load_pages(PAGES_ROOT)
            if not pages:
                return ToolResult(content=[TextContent(type="text", text="No wiki pages found")])
            lines = [f"{page['name']} — {_page_title(page)} ({_summarize_meta(page['meta'])})" for page in pages]
            return ToolResult(content=[TextContent(type="text", text="\n".join(lines))])

        if name == "wiki_search":
            query = args.get("query")
            if not query:
                return ToolResult(
                    content=[TextContent(type="text", text="Error: query is required")],
                    is_error=True,
                )
            limit = min(max(int(args.get("limit", SEARCH["default_limit"])), 1), SEARCH["max_results"])
            results = _search_pages(PAGES_ROOT, query, limit)
            if not results:
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text="No matching wiki pages. Try wiki_list_pages to browse the catalog.",
                        )
                    ]
                )
            return ToolResult(content=[TextContent(type="text", text=_format_search_results(results))])

        if name == "wiki_get_page":
            page_name = args.get("name")
            if not page_name:
                return ToolResult(
                    content=[TextContent(type="text", text="Error: name is required")],
                    is_error=True,
                )
            resolved = _resolve_page(PAGES_ROOT, page_name)
            if resolved is None:
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Error: page not found or path outside wiki directory: {page_name}",
                        )
                    ],
                    is_error=True,
                )
            return ToolResult(content=[TextContent(type="text", text=resolved.read_text(encoding="utf-8"))])

        return ToolResult(
            content=[TextContent(type="text", text=f"Error: Unknown tool {name}")],
            is_error=True,
        )
    except Exception:
        logger.exception(f"Error executing tool {name}")
        return ToolResult(
            content=[TextContent(type="text", text="Error: Wiki operation failed")],
            is_error=True,
        )
