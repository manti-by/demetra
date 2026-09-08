import ast
import logging
from dataclasses import dataclass
from pathlib import Path

from mcp.types import TextContent, Tool

from demetra.settings import SEARCH
from demetra.tools.result import ToolResult
from demetra.tools.search import tokenize


logger = logging.getLogger(__name__)

DOCSTRING_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DocumentedFunction:
    """Represent a function and its docstring extracted from source code."""

    qualified_name: str
    path: str
    line: int
    docstring: str


_cached_fingerprint: tuple[tuple[str, int, int], ...] | None = None
_cached_functions: list[DocumentedFunction] = []
_cached_source_root: Path | None = None


def _source_files(source_root: Path) -> list[Path]:
    """Return Python source files in deterministic order.

    Args:
        source_root: Root directory containing project Python modules.

    Returns:
        list[Path]: Sorted Python source file paths.
    """
    return sorted(path for path in source_root.rglob("*.py") if "__pycache__" not in path.parts)


def _fingerprint(files: list[Path], source_root: Path) -> tuple[tuple[str, int, int], ...]:
    """Build a change fingerprint for source files.

    Args:
        files: Python source files to fingerprint.
        source_root: Root directory used to create relative paths.

    Returns:
        tuple[tuple[str, int, int], ...]: Relative paths, modification times,
            and sizes for cache invalidation.
    """
    return tuple((str(path.relative_to(source_root)), path.stat().st_mtime_ns, path.stat().st_size) for path in files)


def _module_name(path: Path, source_root: Path) -> str:
    """Convert a source path to its dotted module name.

    Args:
        path: Python source file path.
        source_root: Root directory containing the source file.

    Returns:
        str: Dotted module name relative to the source root.
    """
    relative = path.relative_to(source_root).with_suffix("")
    parts = relative.parts[:-1] if relative.name == "__init__" else relative.parts
    return ".".join((source_root.name, *parts))


class _FunctionCollector(ast.NodeVisitor):
    """Collect documented functions while retaining their qualified names."""

    def __init__(self, module_name: str, path: str) -> None:
        """Initialize the collector for one parsed source file.

        Args:
            module_name: Dotted name of the current module.
            path: Project-relative source path.
        """
        self.module_name = module_name
        self.path = path
        self.scope: list[str] = []
        self.functions: list[DocumentedFunction] = []

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Record a documented function and recursively inspect nested scopes.

        Args:
            node: Function syntax node to inspect.
        """
        self.scope.append(node.name)
        docstring = ast.get_docstring(node, clean=True)
        if docstring:
            name_parts = [self.module_name, *self.scope] if self.module_name else self.scope
            self.functions.append(
                DocumentedFunction(
                    qualified_name=".".join(name_parts),
                    path=self.path,
                    line=node.lineno,
                    docstring=docstring,
                )
            )
        self.generic_visit(node)
        self.scope.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Inspect class methods under the class-qualified scope."""
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit a synchronous function definition."""
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit an asynchronous function definition."""
        self._visit_function(node)


def _load_functions(source_root: Path) -> list[DocumentedFunction]:
    """Extract all function docstrings from the project source tree.

    The parsed index is retained in memory and rebuilt only when a Python
    source file is added, removed, or changes its modification time or size.

    Args:
        source_root: Root directory containing project Python modules.

    Returns:
        list[DocumentedFunction]: Documented functions in source-path order.
    """
    global _cached_fingerprint, _cached_functions, _cached_source_root

    files = _source_files(source_root)
    fingerprint = _fingerprint(files, source_root)
    if source_root == _cached_source_root and fingerprint == _cached_fingerprint:
        return _cached_functions

    functions: list[DocumentedFunction] = []
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            logger.warning(f"Unable to parse docstrings from {path}")
            continue
        collector = _FunctionCollector(
            module_name=_module_name(path, source_root),
            path=str(path.relative_to(source_root.parent)),
        )
        collector.visit(tree)
        functions.extend(collector.functions)

    _cached_fingerprint = fingerprint
    _cached_functions = functions
    _cached_source_root = source_root
    return functions


def _score_function(function: DocumentedFunction, terms: list[str]) -> int:
    """Score a documented function against query terms.

    Args:
        function: Documented function to score.
        terms: Search terms to match.

    Returns:
        int: Cumulative relevance score.
    """
    name = function.qualified_name.lower()
    path = function.path.lower()
    docstring = function.docstring.lower()
    return sum(
        SEARCH["docstring_name_weight"] * name.count(term)
        + SEARCH["docstring_path_weight"] * path.count(term)
        + docstring.count(term)
        for term in terms
    )


def _search_functions(source_root: Path, query: str, limit: int) -> list[tuple[DocumentedFunction, int, list[str]]]:
    """Search the compiled function-docstring index.

    Args:
        source_root: Root directory containing project Python modules.
        query: Raw keyword search query.
        limit: Maximum number of results.

    Returns:
        list[tuple[DocumentedFunction, int, list[str]]]: Ranked functions,
            their scores, and the normalized query terms.
    """
    terms = tokenize(query=query)
    if not terms:
        return []
    results = [
        (function, score, terms)
        for function in _load_functions(source_root)
        if (score := _score_function(function, terms)) > 0
    ]
    return sorted(results, key=lambda result: (-result[1], result[0].qualified_name))[:limit]


def _snippets(docstring: str, terms: list[str]) -> list[str]:
    """Extract relevant docstring lines for a search result.

    Args:
        docstring: Docstring text to search.
        terms: Normalized query terms.

    Returns:
        list[str]: Relevant, line-numbered snippets.
    """
    lines = [
        (-sum(line.lower().count(term) for term in terms), line_number, line.strip())
        for line_number, line in enumerate(docstring.splitlines(), start=1)
        if line.strip() and any(term in line.lower() for term in terms)
    ]
    lines.sort()
    selected = sorted(lines[: SEARCH["max_snippets"]], key=lambda line: line[1])
    return [f"L{line_number}: {line[: SEARCH['snippet_length']]}" for _, line_number, line in selected]


AVAILABLE_TOOLS = [
    Tool(
        name="docstring_search",
        description=(
            "Search documented project functions and methods. Returns ranked qualified names, source locations, "
            "and matching docstring snippets; use docstring_get to retrieve a full docstring."
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
        name="docstring_get",
        description="Get a full function or method docstring by the qualified name returned by docstring_search.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Qualified function name, e.g. demetra.tools.wiki.call_tool",
                },
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="docstring_list",
        description="List documented project functions and methods with their qualified names and source locations.",
        input_schema={"type": "object", "properties": {}},
    ),
]


async def list_tools() -> list[Tool]:
    """Return the docstring MCP tool definitions."""
    return AVAILABLE_TOOLS


async def call_tool(name: str, arguments: dict | None) -> ToolResult:
    """Dispatch a docstring MCP tool call by name.

    Args:
        name: Name of the docstring tool to invoke.
        arguments: Optional tool arguments.

    Returns:
        ToolResult: Tool output or an error result.
    """
    args = arguments or {}
    try:
        if not DOCSTRING_ROOT.is_dir():
            return ToolResult(
                content=[TextContent(type="text", text="Project source directory not found")],
                is_error=True,
            )
        functions = _load_functions(DOCSTRING_ROOT)
        if name == "docstring_list":
            if not functions:
                return ToolResult(content=[TextContent(type="text", text="No documented functions found")])
            text = "\n".join(f"{function.qualified_name} — {function.path}:L{function.line}" for function in functions)
            return ToolResult(content=[TextContent(type="text", text=text)])
        if name == "docstring_search":
            query = args.get("query")
            if not query:
                return ToolResult(
                    content=[TextContent(type="text", text="Error: query is required")],
                    is_error=True,
                )
            limit = min(max(int(args.get("limit", SEARCH["default_limit"])), 1), SEARCH["max_results"])
            results = _search_functions(DOCSTRING_ROOT, query, limit)
            if not results:
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text="No matching documented functions. Try docstring_list to browse the catalog.",
                        )
                    ]
                )
            blocks = []
            for position, (function, score, terms) in enumerate(results, start=1):
                snippets = "\n".join(f"   > {snippet}" for snippet in _snippets(function.docstring, terms))
                blocks.append(
                    f"{position}. {function.qualified_name} (score {score})\n"
                    f"   {function.path}:L{function.line}\n{snippets}"
                )
            return ToolResult(content=[TextContent(type="text", text="\n\n".join(blocks))])
        if name == "docstring_get":
            qualified_name = args.get("name")
            if not qualified_name:
                return ToolResult(
                    content=[TextContent(type="text", text="Error: name is required")],
                    is_error=True,
                )
            function = next((item for item in functions if item.qualified_name == qualified_name), None)
            if function is None:
                return ToolResult(
                    content=[TextContent(type="text", text=f"Error: documented function not found: {qualified_name}")],
                    is_error=True,
                )
            text = f"{function.qualified_name}\n{function.path}:L{function.line}\n\n{function.docstring}"
            return ToolResult(content=[TextContent(type="text", text=text)])
        return ToolResult(content=[TextContent(type="text", text=f"Error: Unknown tool {name}")], is_error=True)
    except (OSError, TypeError, ValueError):
        logger.exception(f"Error executing tool {name}")
        return ToolResult(
            content=[TextContent(type="text", text="Error: Docstring operation failed")],
            is_error=True,
        )
