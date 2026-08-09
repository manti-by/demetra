from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from demetra.services.runtime.utils import (
    env_get_bool,
    env_get_int,
    env_get_list,
    env_get_path,
    env_get_str,
    live_stream,
)


class TestUtilsService:
    @pytest.mark.asyncio
    async def test_live_stream_reads_lines(self):
        mock_stream = AsyncMock()
        mock_stream.readline = AsyncMock(side_effect=[b"line 1\n", b"line 2\n", b""])

        result = []
        await live_stream(mock_stream, result=result)

        assert len(result) == 2
        assert "line 1" in result[0]
        assert "line 2" in result[1]

    @pytest.mark.asyncio
    async def test_live_stream_handles_empty_stream(self):
        mock_stream = AsyncMock()
        mock_stream.readline = AsyncMock(side_effect=[b""])

        result = []
        await live_stream(mock_stream, result=result)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_live_stream_stops_on_empty_line(self):
        mock_stream = AsyncMock()
        mock_stream.readline = AsyncMock(side_effect=[b"line\n", b"", b"more data\n"])

        result = []
        await live_stream(mock_stream, result=result)

        assert len(result) == 1
        assert "line" in result[0]


class TestEnvHelpers:
    def test_env_get_bool_returns_true(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL", "true")
        assert env_get_bool("TEST_BOOL", False) is True

    def test_env_get_bool_returns_true_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL", "TRUE")
        assert env_get_bool("TEST_BOOL", False) is True

    def test_env_get_bool_returns_false(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL", "false")
        assert env_get_bool("TEST_BOOL", True) is False

    def test_env_get_bool_returns_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("TEST_BOOL", raising=False)
        assert env_get_bool("TEST_BOOL", True) is True

    def test_env_get_bool_returns_default_when_invalid(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL", "yes")
        assert env_get_bool("TEST_BOOL", True) is True

    def test_env_get_list_returns_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("TEST_LIST", raising=False)
        assert env_get_list("TEST_LIST", ["a", "b"]) == ["a", "b"]

    def test_env_get_list_parses_populated_values(self, monkeypatch):
        monkeypatch.setenv("TEST_LIST", " a ,b ,c ")
        assert env_get_list("TEST_LIST", ["x"]) == ["a", "b", "c"]

    def test_env_get_list_returns_empty_for_explicitly_empty(self, monkeypatch):
        monkeypatch.setenv("TEST_LIST", "")
        assert env_get_list("TEST_LIST", ["x"]) == []

    def test_env_get_str_returns_value(self, monkeypatch):
        monkeypatch.setenv("TEST_STR", "hello")
        assert env_get_str("TEST_STR", "fallback") == "hello"

    def test_env_get_str_returns_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("TEST_STR", raising=False)
        assert env_get_str("TEST_STR", "fallback") == "fallback"

    def test_env_get_str_returns_none_when_unset_without_default(self, monkeypatch):
        monkeypatch.delenv("TEST_STR", raising=False)
        assert env_get_str("TEST_STR", None) is None

    def test_env_get_path_returns_value(self, monkeypatch):
        monkeypatch.setenv("TEST_PATH", "/tmp/foo")
        assert env_get_path("TEST_PATH", None) == Path("/tmp/foo").resolve()

    def test_env_get_path_returns_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("TEST_PATH", raising=False)
        assert env_get_path("TEST_PATH", Path("/var/fallback")) == Path("/var/fallback")

    def test_env_get_path_returns_none_when_unset_without_default(self, monkeypatch):
        monkeypatch.delenv("TEST_PATH", raising=False)
        assert env_get_path("TEST_PATH", None) is None

    def test_env_get_int_returns_value(self, monkeypatch):
        monkeypatch.setenv("TEST_INT", "42")
        assert env_get_int("TEST_INT", 7) == 42

    def test_env_get_int_returns_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("TEST_INT", raising=False)
        assert env_get_int("TEST_INT", 7) == 7

    def test_env_get_int_returns_default_when_invalid(self, monkeypatch):
        monkeypatch.setenv("TEST_INT", "abc")
        assert env_get_int("TEST_INT", 7) == 7

    def test_env_get_int_returns_default_when_negative(self, monkeypatch):
        monkeypatch.setenv("TEST_INT", "-1")
        assert env_get_int("TEST_INT", 7) == 7
