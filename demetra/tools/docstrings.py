import ast
import logging
from pathlib import Path

from mcp.types import TextContent, Tool

from demetra.settings import SEARCH
from demetra.tools.config import SOURCE_ROOT
from demetra.tools.corpus import CorpusCache, rank
from demetra.tools.models import DocumentedFunction, Field, FieldCounts, ToolResult
from demetra.tools.search import count_field, line_hits, tokenize
from demetra.tools.utils import resolve_limit


logger = logging.getLogger(__name__)

# Index the project's application package: the tool answers questions about the
# host codebase, and ``SOURCE_ROOT.name`` prefixes every qualified name
# (``demetra.tools...``).
DOCSTRING_ROOT = SOURCE_ROOT

DOCSTRING_FIELDS = (
    Field(weight=SEARCH["docstring_name_boost"], length_norm=SEARCH["docstring_name_length_norm"]),
    Field(weight=SEARCH["docstring_path_boost"], length_norm=SEARCH["docstring_path_length_norm"]),
    Field(weight=SEARCH["docstring_text_boost"], length_norm=SEARCH["docstring_text_length_norm"]),
)


def list_source_files(source_root: Path) -> list[Path]:
    """Return Python source files in deterministic order.

    Args:
        source_root: Root directory containing project Python modules.

    Returns:
        list[Path]: Sorted Python source file paths.
    """
    return sorted(path for path in source_root.rglob("*.py") if "__pycache__" not in path.parts)


def resolve_module_name(path: Path, source_root: Path) -> str:
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


class FunctionCollector(ast.NodeVisitor):
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

    def visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
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
        self.visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit an asynchronous function definition."""
        self.visit_function(node)


def function_fields(function: DocumentedFunction) -> tuple[FieldCounts, ...]:
    """Count searchable tokens in a function's name, path and docstring zones.

    The qualified name's dots are expanded to spaces so that a bare function or
    method name ("queue_task") reaches the highest-weighted name field; left
    joined, the whole dotted name would be a single token and searching for any
    part of it would match nothing.

    Args:
        function: The documented function to tokenize.

    Returns:
        tuple[FieldCounts, ...]: Field counts aligned to ``DOCSTRING_FIELDS``.
    """
    return (
        count_field(text=function.qualified_name.replace(".", " ")),
        count_field(text=function.path),
        count_field(text=function.docstring),
    )


def _parse_functions(source_root: Path) -> tuple[list[DocumentedFunction], list[tuple[FieldCounts, ...]]]:
    """Parse every documented function under a source root.

    Args:
        source_root: Root directory containing project Python modules.

    Returns:
        tuple: The documented functions and their BM25 field counts, aligned by
            position.
    """
    functions: list[DocumentedFunction] = []
    for path in list_source_files(source_root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            logger.warning(f"Unable to parse docstrings from {path}")
            continue

        collector = FunctionCollector(
            module_name=resolve_module_name(path, source_root),
            path=str(path.relative_to(source_root.parent)),
        )
        collector.visit(tree)
        functions.extend(collector.functions)

    return functions, [function_fields(function=function) for function in functions]


FUNCTIONS = CorpusCache(DOCSTRING_FIELDS, _parse_functions)


def load_functions(source_root: Path) -> tuple[DocumentedFunction, ...]:
    """Extract all function docstrings from the project source tree.

    The parsed index and its BM25 field counts are retained in memory and
    rebuilt only when a Python source file is added, removed, or changes its
    modification time or size.

    Args:
        source_root: Root directory containing project Python modules.

    Returns:
        tuple[DocumentedFunction, ...]: Documented functions in source-path
            order.
    """
    return FUNCTIONS.get(source_root).items


def search_functions(source_root: Path, query: str, limit: int) -> list[tuple[DocumentedFunction, float, list[str]]]:
    """Search the compiled function-docstring index.

    Functions are ranked with BM25F across the qualified name, source path and
    docstring fields, so a name match outweighs prose mentions and rare terms
    outweigh ubiquitous ones. Dots in the query are expanded to spaces to match
    how the name field is indexed, so both ``queue_task`` and
    ``Scheduler.queue_task`` reach it.

    Args:
        source_root: Root directory containing project Python modules.
        query: Raw keyword search query.
        limit: Maximum number of results.

    Returns:
        list[tuple[DocumentedFunction, float, list[str]]]: Ranked functions,
            their scores, and the normalized query terms.
    """
    terms = tokenize(query=query.replace(".", " "))
    if not terms:
        return []

    hits = rank(FUNCTIONS.get(source_root), fields=DOCSTRING_FIELDS, terms=terms)
    hits.sort(key=lambda hit: (-hit.score, hit.item.qualified_name))
    return [(hit.item, hit.score, list(hit.terms)) for hit in hits[:limit]]


def extract_snippets(docstring: str, terms: list[str]) -> list[str]:
    """Extract relevant docstring lines for a search result.

    Args:
        docstring: Docstring text to search.
        terms: Normalized query terms.

    Returns:
        list[str]: Relevant, line-numbered snippets.
    """
    lines = []
    for line_number, line in enumerate(docstring.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        hits = line_hits(line=stripped, terms=terms)
        if hits:
            lines.append((-hits, line_number, stripped))

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
                "query": {
                    "type": "string",
                    "description": "Search query (keywords or a question)",
                    "maxLength": SEARCH["max_query_length"],
                },
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
                    "description": f"Qualified function name, e.g. {SOURCE_ROOT.name}.tools.docstrings.load_functions",
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
    """Return the docstring MCP tool definitions.

    Returns:
        list[Tool]: The static list of available docstring tools.
    """
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
        functions = load_functions(DOCSTRING_ROOT)

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
            if not isinstance(query, str):
                return ToolResult(
                    content=[TextContent(type="text", text="Error: query must be a string")],
                    is_error=True,
                )
            if len(query) > SEARCH["max_query_length"]:
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Error: query exceeds maximum length of {SEARCH['max_query_length']} characters",
                        )
                    ],
                    is_error=True,
                )
            limit = resolve_limit(args)
            results = search_functions(source_root=DOCSTRING_ROOT, query=query, limit=limit)
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
                snippets = "\n".join(f"   > {snippet}" for snippet in extract_snippets(function.docstring, terms))
                blocks.append(
                    f"{position}. {function.qualified_name} (score {score:.3f})\n"
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
    except (OSError, TypeError, ValueError, AttributeError):
        logger.exception(f"Error executing tool {name}")
        return ToolResult(
            content=[TextContent(type="text", text="Error: Docstring operation failed")],
            is_error=True,
        )
