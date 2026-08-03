import logging
import re
from pathlib import Path
from typing import Any

import yaml
from mcp.types import TextContent, Tool

from demetra.settings import BASE_PATH
from demetra.tools.result import ToolResult


logger = logging.getLogger(__name__)

WIKI_ROOT = (BASE_PATH / "wiki").resolve()
PAGES_ROOT = WIKI_ROOT / "pages"

DEFAULT_SEARCH_LIMIT = 5
MAX_SEARCH_RESULTS = 20
MAX_SNIPPETS = 3
SNIPPET_LENGTH = 200

TITLE_WEIGHT = 10
METADATA_WEIGHT = 5

STOP_WORDS = frozenset(
    (
        "a",
        "an",
        "and",
        "are",
        "be",
        "been",
        "did",
        "do",
        "does",
        "for",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "what",
        "why",
        "with",
    )
)

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
BARE_DASH_RE = re.compile(r"^(\s*[A-Za-z_][\w]*\s*:\s*)-$", re.MULTILINE)
TERM_RE = re.compile(r"[a-z0-9][a-z0-9_.\-]*")


def _parse_page(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    meta: dict[str, Any] = {}
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


def _load_pages(pages_root: Path) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for path in sorted(pages_root.glob("*.md")):
        page = _parse_page(path)
        if page is not None:
            pages.append(page)
    return pages


def _resolve_page(pages_root: Path, name: str) -> Path | None:
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
    return [term for term in TERM_RE.findall(query.lower()) if term not in STOP_WORDS and len(term) > 1]


def _metadata_text(meta: dict[str, Any]) -> str:
    parts = []
    for key in ("tags", "services", "tickets", "type"):
        value = meta.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))
    return " ".join(parts).lower()


def _score_page(page: dict[str, Any], terms: list[str]) -> int:
    title = str(page["meta"].get("title") or "").lower()
    metadata = _metadata_text(page["meta"])
    body = page["body"].lower()
    score = 0
    for term in terms:
        score += TITLE_WEIGHT * title.count(term)
        score += METADATA_WEIGHT * metadata.count(term)
        score += body.count(term)
    return score


def _extract_snippets(body: str, terms: list[str]) -> list[str]:
    scored: list[tuple[int, int, str]] = []
    for lineno, line in enumerate(body.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        hits = sum(stripped.lower().count(term) for term in terms)
        if hits:
            scored.append((-hits, lineno, stripped))
    scored.sort(key=lambda item: item[0])
    top = scored[:MAX_SNIPPETS]
    top.sort(key=lambda item: item[1])
    return [f"L{lineno}: {text[:SNIPPET_LENGTH]}" for _, lineno, text in top]


def _search_pages(pages_root: Path, query: str, limit: int) -> list[dict[str, Any]]:
    terms = _tokenize(query)
    if not terms:
        return []
    results: list[dict[str, Any]] = []
    for page in _load_pages(pages_root):
        score = _score_page(page, terms)
        if score > 0:
            results.append({"page": page, "score": score, "terms": terms})
    results.sort(key=lambda result: result["score"], reverse=True)
    return results[:limit]


def _summarize_meta(meta: dict[str, Any]) -> str:
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
                    "description": f"Max results (default {DEFAULT_SEARCH_LIMIT}, max {MAX_SEARCH_RESULTS})",
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
    return AVAILABLE_TOOLS


def _format_search_results(results: list[dict[str, Any]]) -> str:
    blocks = []
    for position, result in enumerate(results, start=1):
        page = result["page"]
        snippets = _extract_snippets(page["body"], result["terms"])
        snippet_lines = "\n".join(f"   > {snippet}" for snippet in snippets)
        blocks.append(
            f"{position}. {page['name']} (score {result['score']})\n"
            f"   {_page_title(page)} — {_summarize_meta(page['meta'])}\n"
            f"{snippet_lines}"
        )
    return "\n\n".join(blocks)


async def call_tool(name: str, arguments: dict | None) -> ToolResult:
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
            limit = min(max(int(args.get("limit", DEFAULT_SEARCH_LIMIT)), 1), MAX_SEARCH_RESULTS)
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
