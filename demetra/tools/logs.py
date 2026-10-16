import logging
from pathlib import Path

from mcp.types import TextContent, Tool

from demetra.tools.config import LOG_ROOT_DISPLAY, LOG_ROOT_RESOLVED
from demetra.tools.models import ToolResult


logger = logging.getLogger(__name__)

MAX_TAIL_LINES = 5000
DEFAULT_TAIL_LINES = 100


def resolve_log_path(file_path: str) -> Path | None:
    """Resolve a relative log path and ensure it stays inside the log root.

    Args:
        file_path: Relative path to a log file, e.g. ``"sessions/abc.log"``.

    Returns:
        Path | None: The resolved path if it is a file inside the log
            directory, otherwise None.
    """
    target = (LOG_ROOT_RESOLVED / file_path).resolve()
    try:
        target.relative_to(LOG_ROOT_RESOLVED)
    except ValueError:
        return None
    return target if target.is_file() else None


def tail_file(path: Path, lines: int) -> str:
    """Read the trailing lines of a log file without loading it fully.

    Reads backwards in blocks from the end of the file and decodes only the
    last requested lines.

    Args:
        path: Path of the file to read.
        lines: Number of trailing lines to return, clamped to 1..MAX_TAIL_LINES.

    Returns:
        str: The requested trailing lines, or an empty string for an empty
            file.
    """
    lines = min(max(lines, 1), MAX_TAIL_LINES)
    BLOCK_SIZE = 8192

    with path.open("rb") as f:
        # Size from the open handle, not a separate stat: the file may be
        # truncated between the two calls.
        f.seek(0, 2)
        file_size = f.tell()
        if file_size == 0:
            return ""

        pos = file_size
        buffer = bytearray()
        newline_count = 0

        def complete() -> bool:
            """Whether the buffer holds enough whole lines to answer the request."""
            if newline_count < lines:
                return False
            # A trailing newline terminates the last line, so any line before it
            # is complete. Without one we must also read back past the start of
            # the first requested line, or return a fragment of it.
            return not buffer or buffer[-1:] == b"\n" or b"\n" in buffer[1:-1]

        while pos > 0 and not complete():
            read_size = min(BLOCK_SIZE, pos)
            pos -= read_size
            f.seek(pos)
            chunk = f.read(read_size)
            if not chunk:
                # Truncated after the size was read: stop rather than re-reading
                # the same range once per block for the rest of the file.
                break
            buffer[:0] = chunk
            newline_count += chunk.count(b"\n")

        all_lines = buffer.split(b"\n")
        if buffer[-1:] == b"\n":
            all_lines.pop()

        return b"\n".join(all_lines[-lines:]).decode("utf-8", errors="replace")


AVAILABLE_TOOLS = [
    Tool(
        name="list_log_files",
        description=f"List all log files in {LOG_ROOT_DISPLAY}",
        input_schema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="tail_logs",
        description=f"Tail a log file from the {LOG_ROOT_DISPLAY} directory",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path to log file (e.g. demetra.log, sessions/abc.log)",
                },
                "lines": {
                    "type": "integer",
                    "description": "Number of lines to retrieve (default 100, max 5000)",
                    "default": DEFAULT_TAIL_LINES,
                },
            },
            "required": ["file_path"],
        },
    ),
]


async def list_tools() -> list[Tool]:
    """Return the project/log MCP tool definitions.

    Returns:
        list[Tool]: The static list of available log tools.
    """
    return AVAILABLE_TOOLS


async def call_tool(name: str, arguments: dict | None) -> ToolResult:
    """Dispatch a project log MCP tool call by name.

    Handles listing log files and tailing individual log files, wrapping both
    results and errors into a ToolResult.

    Args:
        name: The name of the log tool to invoke.
        arguments: Optional tool arguments as a mapping.

    Returns:
        ToolResult: The tool output, or an error result on failure.
    """
    args = arguments or {}
    try:
        if name == "list_log_files":
            if not LOG_ROOT_RESOLVED.is_dir():
                return ToolResult(
                    content=[TextContent(type="text", text=f"Log directory not found: {LOG_ROOT_DISPLAY}")],
                    is_error=True,
                )
            files = sorted(LOG_ROOT_RESOLVED.rglob("*.log"))
            result = []
            for f in files:
                # rglob follows symlinks, so a link inside the root can point
                # outside it; confine before reading any metadata.
                resolved = f.resolve()
                try:
                    rel = resolved.relative_to(LOG_ROOT_RESOLVED)
                except ValueError:
                    continue
                if not resolved.is_file():
                    continue
                metadata = resolved.stat()
                result.append(f"{rel}  ({metadata.st_size:,} bytes, modified {metadata.st_mtime:.0f})")
            if not result:
                return ToolResult(content=[TextContent(type="text", text="No log files found")])
            return ToolResult(content=[TextContent(type="text", text="\n".join(result))])

        if name == "tail_logs":
            file_path = args.get("file_path")
            if not file_path:
                return ToolResult(
                    content=[TextContent(type="text", text="Error: file_path is required")],
                    is_error=True,
                )
            resolved = resolve_log_path(file_path)
            if resolved is None:
                return ToolResult(
                    content=[
                        TextContent(
                            type="text", text=f"Error: file not found or path outside log directory: {file_path}"
                        )
                    ],
                    is_error=True,
                )
            lines = args.get("lines", DEFAULT_TAIL_LINES)
            content = tail_file(resolved, lines)
            return ToolResult(content=[TextContent(type="text", text=content)])

        return ToolResult(
            content=[TextContent(type="text", text=f"Error: Unknown tool {name}")],
            is_error=True,
        )
    except Exception:
        logger.exception(f"Error executing tool {name}")
        return ToolResult(
            content=[TextContent(type="text", text="Error: Log operation failed")],
            is_error=True,
        )
