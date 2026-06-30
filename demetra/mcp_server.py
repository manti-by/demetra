import asyncio
import logging.config
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from demetra.settings import LOGGING
from demetra.tools import call_tool, list_tools


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)

APP_NAME = "Demetra MCP Server"
VERSION = "1.0.0"


mcp_server = Server(APP_NAME)


@mcp_server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return await list_tools()


@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    return await call_tool(name, arguments)


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options(),
        )


if __name__ == "__main__":
    print(f"Starting {APP_NAME} v{VERSION}", file=sys.stderr)
    asyncio.run(main())
