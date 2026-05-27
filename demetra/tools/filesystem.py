import fnmatch
import logging
import shutil
from pathlib import Path

from mcp.server import Server
from mcp.types import TextContent, Tool

from demetra.settings import BASE_PATH


logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 1024 * 1024

SENSITIVE_PATTERNS = (
    ".env",
    ".env.*",
    ".git",
    ".gitignore",
    ".DS_Store",
    "*.pem",
    "*.key",
    "*.sqlite*",
    "*.db",
    "config.yaml",
    "config.yml",
    "secrets.yaml",
    "secrets.yml",
    "credentials.json",
)


def _is_sensitive_path(path: Path) -> bool:
    path_str = str(path)
    name = path.name
    for pattern in SENSITIVE_PATTERNS:
        if "*" in pattern:
            if fnmatch.fnmatch(name, pattern):
                return True
        elif pattern in path_str or name == pattern or name == f".{pattern}":
            return True
    return False


async def read_file(path: str, cwd: Path | None = None) -> list:
    base = cwd or BASE_PATH
    file_path = base / path
    try:
        resolved = file_path.resolve()
        resolved.relative_to(base)
    except ValueError:
        return [TextContent(type="text", text="Error: Path outside allowed directory")]

    if _is_sensitive_path(resolved):
        return [TextContent(type="text", text="Error: Access to sensitive files is denied")]

    if not resolved.exists():
        return [TextContent(type="text", text="Error: File not found")]

    if resolved.is_dir():
        return [TextContent(type="text", text="Error: Path is a directory, use list_directory")]

    file_size = resolved.stat().st_size
    if file_size > MAX_FILE_SIZE:
        return [
            TextContent(type="text", text=f"Error: File too large ({file_size} bytes). Max size: {MAX_FILE_SIZE} bytes")
        ]

    try:
        content = resolved.read_text()
        return [TextContent(type="text", text=content)]
    except (OSError, UnicodeDecodeError) as e:
        return [TextContent(type="text", text=f"Error reading file: {e}")]


async def write_file(path: str, content: str, cwd: Path | None = None) -> list:
    base = cwd or BASE_PATH
    file_path = base / path
    try:
        resolved = file_path.resolve()
        resolved.relative_to(base)
    except ValueError:
        return [TextContent(type="text", text="Error: Path outside allowed directory")]

    if _is_sensitive_path(resolved):
        return [TextContent(type="text", text="Error: Access to sensitive files is denied")]

    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content)
        return [TextContent(type="text", text=f"Successfully wrote to {path}")]
    except OSError as e:
        return [TextContent(type="text", text=f"Error writing file: {e}")]


async def delete_file(path: str, cwd: Path | None = None) -> list:
    base = cwd or BASE_PATH
    file_path = base / path
    try:
        resolved = file_path.resolve()
        resolved.relative_to(base)
    except ValueError:
        return [TextContent(type="text", text="Error: Path outside allowed directory")]

    if _is_sensitive_path(resolved):
        return [TextContent(type="text", text="Error: Access to sensitive files is denied")]

    if not resolved.exists():
        return [TextContent(type="text", text="Error: File not found")]

    if resolved == base:
        return [TextContent(type="text", text="Error: Cannot delete the root directory")]

    try:
        if resolved.is_dir():
            shutil.rmtree(resolved)
        else:
            resolved.unlink()
        return [TextContent(type="text", text=f"Successfully deleted {path}")]
    except OSError as e:
        return [TextContent(type="text", text=f"Error deleting: {e}")]


async def list_directory(path: str = "", cwd: Path | None = None) -> list:
    base = cwd or BASE_PATH
    dir_path = base / path
    try:
        resolved = dir_path.resolve()
        resolved.relative_to(base)
    except ValueError:
        return [TextContent(type="text", text="Error: Path outside allowed directory")]

    if not resolved.exists():
        return [TextContent(type="text", text="Error: Directory not found")]

    if not resolved.is_dir():
        return [TextContent(type="text", text="Error: Path is not a directory")]

    try:
        entries = []
        for entry in resolved.iterdir():
            if _is_sensitive_path(entry):
                continue
            entries.append(
                {
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                }
            )
        return [TextContent(type="text", text=str(entries))]
    except OSError as e:
        return [TextContent(type="text", text=f"Error listing directory: {e}")]


_TOOLS = [
    Tool(
        name="read_file",
        description="Read a file from the filesystem",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="write_file",
        description="Write content to a file",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "content": {"type": "string", "description": "Content to write"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
            "required": ["path", "content"],
        },
    ),
    Tool(
        name="delete_file",
        description="Delete a file or directory",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to delete"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="list_directory",
        description="List directory contents",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (empty for root)"},
                "auth_token": {"type": "string", "description": "Optional auth token"},
            },
        },
    ),
]


async def _list_tools() -> list[Tool]:
    return _TOOLS


async def _call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    args = arguments or {}
    if name == "read_file":
        path = args.get("path")
        if not path:
            return [TextContent(type="text", text="Error: path is required")]
        return await read_file(path, BASE_PATH)
    if name == "write_file":
        path = args.get("path")
        content = args.get("content")
        if not path or content is None:
            return [TextContent(type="text", text="Error: path and content are required")]
        return await write_file(path, content, BASE_PATH)
    if name == "delete_file":
        path = args.get("path")
        if not path:
            return [TextContent(type="text", text="Error: path is required")]
        return await delete_file(path, BASE_PATH)
    if name == "list_directory":
        path = args.get("path", "")
        return await list_directory(path, BASE_PATH)
    return [TextContent(type="text", text=f"Error: Unknown tool {name}")]


def create_filesystem_tools(mcp: Server) -> None:
    @mcp.list_tools()
    async def list_tools() -> list[Tool]:
        return await _list_tools()

    @mcp.call_tool()
    async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        return await _call_tool(name, arguments)
