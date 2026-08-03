from dataclasses import dataclass

from mcp.types import TextContent


@dataclass
class ToolResult:
    content: list[TextContent]
    is_error: bool = False
