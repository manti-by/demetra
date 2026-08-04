import asyncio
import logging.config
import sys

from mcp.server import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
)

from demetra.settings import LOGGING
from demetra.tools import call_tool, list_tools


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)

APP_NAME = "Demetra MCP Server"
VERSION = "1.0.0"


async def handle_list_tools(
    ctx: ServerRequestContext,
    params: PaginatedRequestParams | None,
) -> ListToolsResult:
    """Handle the MCP ``list_tools`` request.

    Args:
        ctx: The MCP server request context.
        params: Pagination parameters, if any.

    Returns:
        ListToolsResult: The aggregated tool definitions.
    """
    tools = await list_tools()
    return ListToolsResult(tools=tools)


async def handle_call_tool(
    ctx: ServerRequestContext,
    params: CallToolRequestParams,
) -> CallToolResult:
    """Handle the MCP ``call_tool`` request.

    Args:
        ctx: The MCP server request context.
        params: The tool name and arguments to invoke.

    Returns:
        CallToolResult: The tool call outcome.
    """
    result = await call_tool(params.name, params.arguments)
    return CallToolResult(content=result.content, is_error=result.is_error)


mcp_server = Server(
    APP_NAME,
    version=VERSION,
    on_list_tools=handle_list_tools,
    on_call_tool=handle_call_tool,
)


async def main():
    """Run the MCP server over stdio until the transport closes.

    Serves the registered tool handlers over a stdio JSON-RPC transport.
    """
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options(),
        )


if __name__ == "__main__":
    print(f"Starting {APP_NAME} v{VERSION}", file=sys.stderr)
    asyncio.run(main())
