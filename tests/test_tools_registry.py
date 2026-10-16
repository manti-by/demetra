import pytest

from demetra.tools import database, docstrings, logs
from demetra.tools.registry import HANDLERS, call_tool, list_tools


class TestListTools:
    async def test_registered_names_match_handlers(self):
        assert {tool.name for tool in await list_tools()} == set(HANDLERS)

    async def test_names_are_unique(self):
        names = [tool.name for tool in await list_tools()]
        assert len(names) == len(set(names))

    async def test_every_tool_declares_an_object_schema(self):
        for tool in await list_tools():
            assert tool.input_schema["type"] == "object", tool.name

    @pytest.mark.parametrize(
        "module", [database, docstrings, logs], ids=lambda module: module.__name__.rsplit(".", 1)[-1]
    )
    async def test_module_listers_match_registered_handlers(self, module):
        for tool in await module.list_tools():
            assert HANDLERS[tool.name] is module.call_tool


class TestCallTool:
    async def test_unknown_tool_is_an_error_not_a_crash(self):
        result = await call_tool("no_such_tool", {})
        assert result.is_error
        assert "Unknown tool no_such_tool" in result.content[0].text

    async def test_missing_arguments_are_tolerated(self):
        result = await call_tool("list_log_files", None)
        assert isinstance(result.content, list)
