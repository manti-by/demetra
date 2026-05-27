import asyncio
import logging.config
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server

from demetra.settings import LOGGING
from demetra.tools import create_database_tools, create_filesystem_tools


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)

APP_NAME = "Demetra MCP Server"
VERSION = "1.0.0"


mcp_server = Server(APP_NAME)

create_database_tools(mcp_server)
create_filesystem_tools(mcp_server)


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
