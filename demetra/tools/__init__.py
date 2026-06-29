from demetra.tools.database import call_tool as _call_database_tool
from demetra.tools.database import list_tools as _list_database_tools
from demetra.tools.projects import call_tool as _call_projects_tool
from demetra.tools.projects import list_tools as _list_projects_tools


__all__: list[str] = []


async def list_tools() -> list:
    db = await _list_database_tools()
    proj = await _list_projects_tools()
    return db + proj


async def call_tool(name: str, arguments: dict | None) -> list:
    db_tools = await _list_database_tools()
    db_names = {t.name for t in db_tools}
    if name in db_names:
        return await _call_database_tool(name, arguments)
    return await _call_projects_tool(name, arguments)
