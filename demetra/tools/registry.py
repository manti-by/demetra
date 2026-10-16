from collections.abc import Awaitable, Callable

from mcp.types import TextContent, Tool

import demetra.tools.database as database
import demetra.tools.docstrings as docstrings
import demetra.tools.logs as logs
from demetra.tools.models import ToolResult


ToolHandler = Callable[[str, dict | None], Awaitable[ToolResult]]
ToolLister = Callable[[], Awaitable[list[Tool]]]

# (tool list coroutine, dispatch coroutine, static tool definitions) per module.
MODULES: tuple[tuple[ToolLister, ToolHandler, list[Tool]], ...] = (
    (database.list_tools, database.call_tool, database.AVAILABLE_TOOLS),
    (docstrings.list_tools, docstrings.call_tool, docstrings.AVAILABLE_TOOLS),
    (logs.list_tools, logs.call_tool, logs.AVAILABLE_TOOLS),
)

HANDLERS: dict[str, ToolHandler] = {tool.name: handler for _, handler, tools in MODULES for tool in tools}


async def list_tools() -> list[Tool]:
    """Return the aggregated tool definitions from all tool modules.

    Returns:
        list[Tool]: The concatenated tool lists of every tool module.
    """
    tools: list[Tool] = []
    for lister, _, _ in MODULES:
        tools.extend(await lister())
    return tools


async def call_tool(name: str, arguments: dict | None) -> ToolResult:
    """Dispatch a tool call to the module that owns the named tool.

    Args:
        name: The name of the MCP tool to invoke.
        arguments: Optional tool arguments as a mapping.

    Returns:
        ToolResult: The outcome of the underlying tool call, or an error result
            when no module declares the name.
    """
    handler = HANDLERS.get(name)
    if handler is None:
        return ToolResult(
            content=[TextContent(type="text", text=f"Error: Unknown tool {name}")],
            is_error=True,
        )
    return await handler(name, arguments)
