from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.llm.parser import NumberedListOutputParser
from demetra.services.llm.prompt import get_prompt
from demetra.services.persistence.queue import queue


class TestPrompt:
    @pytest.mark.asyncio
    async def test_get_prompt_without_kwargs(self):
        content = "Hello world"
        with (
            patch("demetra.services.llm.prompt.aiofiles.open") as mock_open,
        ):
            mock_file = AsyncMock()
            mock_file.__aenter__.return_value = mock_file
            mock_file.read = AsyncMock(return_value=content)
            mock_open.return_value = mock_file

            result = await get_prompt("test")
            assert result == content

    @pytest.mark.asyncio
    async def test_get_prompt_with_kwargs(self):
        content = "Hello {subject}"
        with (
            patch("demetra.services.llm.prompt.aiofiles.open") as mock_open,
        ):
            mock_file = AsyncMock()
            mock_file.__aenter__.return_value = mock_file
            mock_file.read = AsyncMock(return_value=content)
            mock_open.return_value = mock_file

            result = await get_prompt("test", subject="World")
            assert result == "Hello World"


class TestParser:
    def test_parse_numbered_list_simple(self):
        parser = NumberedListOutputParser()
        result = parser.parse("1. First item\n2. Second item")
        assert result == ["First item", "Second item"]

    def test_parse_numbered_list_with_parentheses(self):
        parser = NumberedListOutputParser()
        result = parser.parse("1) First item\n2) Second item")
        assert result == ["First item", "Second item"]

    def test_parse_numbered_list_no_numbers(self):
        parser = NumberedListOutputParser()
        result = parser.parse("First item\nSecond item")
        assert result == ["First item", "Second item"]

    def test_parse_numbered_list_empty_lines(self):
        parser = NumberedListOutputParser()
        result = parser.parse("1. First item\n\n2. Second item")
        assert result == ["First item", "Second item"]

    def test_parser_type(self):
        parser = NumberedListOutputParser()
        assert parser._type == "numbered_list"


class TestQueue:
    def test_queue_exists(self):
        assert queue is not None


class TestTuiPrintHeading:
    @pytest.mark.asyncio
    async def test_print_heading_calls_console(self):
        with patch("demetra.services.runtime.tui.console") as mock_console:
            from demetra.services.runtime.tui import print_heading

            await print_heading()
            mock_console.print.assert_called_once()


class TestGraphqlGetQuery:
    @pytest.mark.asyncio
    async def test_get_query_returns_content(self):
        with (
            patch("demetra.services.linear.graphql.aiofiles.open") as mock_open,
        ):
            mock_file = AsyncMock()
            mock_file.__aenter__.return_value = mock_file
            mock_file.read = AsyncMock(return_value="query { issues { id } }")
            mock_open.return_value = mock_file

            from demetra.services.linear.graphql import get_query

            result = await get_query("test_query")
            assert result == "query { issues { id } }"
