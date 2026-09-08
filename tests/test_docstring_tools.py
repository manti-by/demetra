from demetra.tools import docstrings


SOURCE = '''\
"""Example module."""


def deploy_worker():
    """Deploy a worker to the configured runtime."""


class Scheduler:
    def queue_task(self):
        """Queue a task for asynchronous execution."""
'''


class TestDocstringIndex:
    def test_loads_documented_functions(self, tmp_path):
        source_root = tmp_path / "demetra"
        source_root.mkdir()
        (source_root / "runtime.py").write_text(SOURCE)

        functions = docstrings._load_functions(source_root)

        assert [function.qualified_name for function in functions] == [
            "demetra.runtime.deploy_worker",
            "demetra.runtime.Scheduler.queue_task",
        ]
        assert functions[0].path == "demetra/runtime.py"

    def test_rebuilds_index_when_source_changes(self, tmp_path):
        source_root = tmp_path / "demetra"
        source_root.mkdir()
        source = source_root / "runtime.py"
        source.write_text(SOURCE)
        first = docstrings._load_functions(source_root)
        source.write_text(SOURCE.replace("Deploy a worker", "Start a worker"))

        second = docstrings._load_functions(source_root)

        assert first[0].docstring == "Deploy a worker to the configured runtime."
        assert second[0].docstring == "Start a worker to the configured runtime."


class TestDocstringTools:
    async def test_list_search_and_get(self, tmp_path, monkeypatch):
        source_root = tmp_path / "demetra"
        source_root.mkdir()
        (source_root / "runtime.py").write_text(SOURCE)
        monkeypatch.setattr(docstrings, "DOCSTRING_ROOT", source_root)

        listed = await docstrings.call_tool("docstring_list", {})
        searched = await docstrings.call_tool("docstring_search", {"query": "asynchronous task"})
        fetched = await docstrings.call_tool("docstring_get", {"name": "demetra.runtime.Scheduler.queue_task"})

        assert "demetra.runtime.deploy_worker" in listed.content[0].text
        assert "demetra.runtime.Scheduler.queue_task" in searched.content[0].text
        assert "Queue a task" in fetched.content[0].text

    async def test_search_requires_query(self, tmp_path, monkeypatch):
        source_root = tmp_path / "demetra"
        source_root.mkdir()
        monkeypatch.setattr(docstrings, "DOCSTRING_ROOT", source_root)

        result = await docstrings.call_tool("docstring_search", {})

        assert result.is_error
        assert "query is required" in result.content[0].text

    async def test_get_rejects_unknown_name(self, tmp_path, monkeypatch):
        source_root = tmp_path / "demetra"
        source_root.mkdir()
        (source_root / "runtime.py").write_text(SOURCE)
        monkeypatch.setattr(docstrings, "DOCSTRING_ROOT", source_root)

        result = await docstrings.call_tool("docstring_get", {"name": "missing.function"})

        assert result.is_error
        assert "not found" in result.content[0].text


class TestToolsRegistration:
    async def test_docstring_tools_registered(self):
        from demetra.tools import list_tools

        names = {tool.name for tool in await list_tools()}

        assert {"docstring_search", "docstring_get", "docstring_list"} <= names
