from unittest.mock import AsyncMock

import pytest

from demetra.services.utils import env_get_bool, env_get_list, live_stream


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
