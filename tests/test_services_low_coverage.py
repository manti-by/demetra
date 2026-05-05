from demetra.services.parser import NumberedListOutputParser
from demetra.services.queue import queue


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
