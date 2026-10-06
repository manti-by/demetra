from demetra.tools.database import call_tool as _call_database_tool
from demetra.tools.database import list_tools as _list_database_tools
from demetra.tools.docstrings import call_tool as _call_docstrings_tool
from demetra.tools.docstrings import list_tools as _list_docstrings_tools
from demetra.tools.projects import call_tool as _call_projects_tool
from demetra.tools.projects import list_tools as _list_projects_tools
from demetra.tools.result import ToolResult
from demetra.tools.wiki import call_tool as _call_wiki_tool
from demetra.tools.wiki import list_tools as _list_wiki_tools


async def list_tools() -> list:
    """Return the aggregated tool definitions from all tool modules.

    Combines the database, docstring, project and wiki MCP tool lists into a single
    response for the MCP server.

    Returns:
        list: The concatenated list of Tool definitions.
    """
    db = await _list_database_tools()
    docstrings = await _list_docstrings_tools()
    proj = await _list_projects_tools()
    wiki = await _list_wiki_tools()
    return db + docstrings + proj + wiki


async def call_tool(name: str, arguments: dict | None) -> ToolResult:
    """Dispatch a tool call to the module that owns the named tool.

    Resolves the tool name against the database, docstring, and wiki tool sets
    first and falls back to the projects module for any remaining names.

    Args:
        name: The name of the MCP tool to invoke.
        arguments: Optional tool arguments as a mapping.

    Returns:
        ToolResult: The outcome of the underlying tool call.
    """
    db_tools = await _list_database_tools()
    db_names = {t.name for t in db_tools}
    if name in db_names:
        return await _call_database_tool(name, arguments)
    docstring_tools = await _list_docstrings_tools()
    docstring_names = {t.name for t in docstring_tools}
    if name in docstring_names:
        return await _call_docstrings_tool(name, arguments)
    wiki_tools = await _list_wiki_tools()
    wiki_names = {t.name for t in wiki_tools}
    if name in wiki_names:
        return await _call_wiki_tool(name, arguments)
    return await _call_projects_tool(name, arguments)
