import pytest

from demetra.tools import wiki


ANSI_PAGE = """---
title: ANSI Color Escapes in Logs
date: 2026-07-20
type: debug
status: resolved
session_id: sess-1
services: [logging]
branch: master
tickets: [MNT-100]
tags: [ansi, logging]
related: []
---

# ANSI Color Escapes in Logs

## TL;DR

ANSI escape codes polluted the log files. Added stripping filters to the logging pipeline.
"""

MCP_PAGE = """---
title: Fix MCP Server for the mcp 2.0 API
date: 2026-08-03
type: debug
status: resolved
session_id:
services: [mcp]
branch: master
tickets: []
tags: [mcp, dependencies, upgrade]
related: []
---

# Fix MCP Server for the mcp 2.0 API

## TL;DR

The mcp 2.0.0 upgrade removed the list_tools decorators from the low-level Server.
Rewrote demetra/mcp_server.py against the new API.
"""


@pytest.fixture
def pages_root(tmp_path, monkeypatch):
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "2026-07-20-resolve-ansi-color-escape-codes-in-logs.md").write_text(ANSI_PAGE)
    (pages_dir / "2026-08-03-fix-mcp-server-2.0-api.md").write_text(MCP_PAGE)
    monkeypatch.setattr(wiki, "PAGES_ROOT", pages_dir)
    return pages_dir


class TestParsePage:
    def test_valid_frontmatter(self, tmp_path):
        path = tmp_path / "page.md"
        path.write_text(ANSI_PAGE)
        page = wiki._parse_page(path)
        assert page is not None
        assert page["name"] == "page.md"
        assert page["meta"]["title"] == "ANSI Color Escapes in Logs"
        assert page["meta"]["tags"] == ["ansi", "logging"]
        assert "stripping filters" in page["body"]
        assert "title:" not in page["body"]

    def test_no_frontmatter(self, tmp_path):
        path = tmp_path / "plain.md"
        path.write_text("# Just a heading\n\nSome body text.")
        page = wiki._parse_page(path)
        assert page is not None
        assert page["meta"] == {}
        assert "Just a heading" in page["body"]

    def test_invalid_frontmatter_skipped(self, tmp_path):
        path = tmp_path / "broken.md"
        path.write_text("---\ntitle: [unclosed\n---\n\nBody")
        assert wiki._parse_page(path) is None

    def test_non_mapping_frontmatter_skipped(self, tmp_path):
        path = tmp_path / "list.md"
        path.write_text("---\n- just\n- a\n- list\n---\n\nBody")
        assert wiki._parse_page(path) is None

    def test_bare_dash_empty_placeholder_accepted(self, tmp_path):
        path = tmp_path / "dash.md"
        path.write_text("---\ntitle: Some page\nbranch: -\ntickets: []\n---\n\nBody")
        page = wiki._parse_page(path)
        assert page is not None
        assert page["meta"]["branch"] == "-"


class TestTokenize:
    def test_stop_words_and_short_terms_removed(self):
        assert wiki._tokenize("Why is the MCP server down?") == ["mcp", "server", "down"]

    def test_keeps_dotted_and_dashed_terms(self):
        assert wiki._tokenize("mcp_server.py on_list_tools") == ["mcp_server.py", "on_list_tools"]


class TestScoring:
    def test_title_match_outranks_body_match(self, pages_root):
        results = wiki._search_pages(pages_root, "mcp", 10)
        assert results[0]["page"]["name"] == "2026-08-03-fix-mcp-server-2.0-api.md"

    def test_body_only_match_still_found(self, pages_root):
        results = wiki._search_pages(pages_root, "stripping filters", 10)
        assert [r["page"]["name"] for r in results] == ["2026-07-20-resolve-ansi-color-escape-codes-in-logs.md"]

    def test_no_terms_returns_empty(self, pages_root):
        assert wiki._search_pages(pages_root, "the and of", 10) == []

    def test_limit_applied(self, pages_root):
        results = wiki._search_pages(pages_root, "the logging pipeline mcp server", limit=1)
        assert len(results) == 1


class TestExtractSnippets:
    def test_returns_best_lines_in_document_order(self):
        body = "first mcp mention\n\nirrelevant\n\nmcp mcp mcp dense line\n\nlast mcp line"
        snippets = wiki._extract_snippets(body, ["mcp"])
        assert snippets[0].startswith("L1:")
        assert snippets[1].startswith("L5:")
        assert "dense line" in snippets[1]

    def test_max_snippets_respected(self):
        body = "\n".join(f"line {i} mentions token" for i in range(10))
        assert len(wiki._extract_snippets(body, ["token"])) == wiki.MAX_SNIPPETS

    def test_long_lines_truncated(self):
        body = "token " + "x" * 500
        snippet = wiki._extract_snippets(body, ["token"])[0]
        assert len(snippet) <= wiki.SNIPPET_LENGTH + len("L1: ")


class TestResolvePage:
    def test_plain_name(self, pages_root):
        resolved = wiki._resolve_page(pages_root, "2026-08-03-fix-mcp-server-2.0-api.md")
        assert resolved is not None and resolved.is_file()

    def test_name_without_extension_and_prefix(self, pages_root):
        resolved = wiki._resolve_page(pages_root, "pages/2026-08-03-fix-mcp-server-2.0-api")
        assert resolved is not None and resolved.is_file()

    def test_path_traversal_rejected(self, pages_root):
        assert wiki._resolve_page(pages_root, "../../pyproject.toml") is None
        assert wiki._resolve_page(pages_root, "../pages/../../pyproject.toml") is None

    def test_missing_page(self, pages_root):
        assert wiki._resolve_page(pages_root, "no-such-page.md") is None


class TestCallTool:
    async def test_list_pages(self, pages_root):
        result = await wiki.call_tool("wiki_list_pages", {})
        assert not result.is_error
        text = result.content[0].text
        assert "2026-08-03-fix-mcp-server-2.0-api.md" in text
        assert "type: debug" in text
        assert "tags: mcp, dependencies, upgrade" in text

    async def test_search_returns_ranked_snippets(self, pages_root):
        result = await wiki.call_tool("wiki_search", {"query": "mcp server crash"})
        assert not result.is_error
        text = result.content[0].text
        assert "1. 2026-08-03-fix-mcp-server-2.0-api.md" in text
        assert ">" in text

    async def test_search_no_match(self, pages_root):
        result = await wiki.call_tool("wiki_search", {"query": "nonexistent xyzzy"})
        assert not result.is_error
        assert "No matching wiki pages" in result.content[0].text

    async def test_search_requires_query(self, pages_root):
        result = await wiki.call_tool("wiki_search", {})
        assert result.is_error
        assert "query is required" in result.content[0].text

    async def test_get_page(self, pages_root):
        result = await wiki.call_tool("wiki_get_page", {"name": "2026-08-03-fix-mcp-server-2.0-api.md"})
        assert not result.is_error
        assert "Fix MCP Server" in result.content[0].text

    async def test_get_page_requires_name(self, pages_root):
        result = await wiki.call_tool("wiki_get_page", {})
        assert result.is_error
        assert "name is required" in result.content[0].text

    async def test_get_page_traversal_rejected(self, pages_root):
        result = await wiki.call_tool("wiki_get_page", {"name": "../../pyproject.toml"})
        assert result.is_error
        assert "outside wiki directory" in result.content[0].text

    async def test_unknown_tool(self, pages_root):
        result = await wiki.call_tool("wiki_delete_everything", {})
        assert result.is_error
        assert "Unknown tool" in result.content[0].text

    async def test_missing_wiki_directory(self, tmp_path, monkeypatch):
        monkeypatch.setattr(wiki, "PAGES_ROOT", tmp_path / "nowhere")
        result = await wiki.call_tool("wiki_list_pages", {})
        assert result.is_error
        assert "not found" in result.content[0].text


class TestToolsRegistration:
    async def test_wiki_tools_registered(self):
        from demetra.tools import call_tool, list_tools

        names = {tool.name for tool in await list_tools()}
        assert {"wiki_search", "wiki_get_page", "wiki_list_pages"} <= names

        result = await call_tool("wiki_search", {"query": "mcp"})
        assert not result.is_error
