from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from demetra.library.exceptions import SettingsError
from demetra.services.runtime.utils import (
    env_get_bool,
    env_get_int,
    env_get_list,
    env_get_path,
    env_get_str,
    is_loopback_host,
    live_stream,
    validate_llm_base_url,
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
        monkeypatch.setenv("TEST_BOOL", "yep")
        assert env_get_bool("TEST_BOOL", True) is True

    def test_env_get_bool_accepts_one_zero_yes_no_on_off(self, monkeypatch):
        for raw, expected in [("1", True), ("0", False), ("yes", True), ("no", False), ("on", True), ("off", False)]:
            monkeypatch.setenv("TEST_BOOL", raw)
            assert env_get_bool("TEST_BOOL", not expected) is expected

    def test_env_get_bool_warns_and_returns_default_for_invalid(self, monkeypatch, caplog):
        monkeypatch.setenv("TEST_BOOL", "definitely-not-a-bool")
        assert env_get_bool("TEST_BOOL", True) is True
        assert "ignoring invalid value" in caplog.text

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

    def test_env_get_int_rejects_negative_default(self, monkeypatch):
        monkeypatch.delenv("TEST_INT", raising=False)
        with pytest.raises(ValueError, match="default must be nonnegative"):
            env_get_int("TEST_INT", -1)


class TestValidateLlmBaseUrl:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://openrouter.ai/api/v1", "https://openrouter.ai/api/v1"),
            ("https://custom.example/v1", "https://custom.example/v1"),
            ("http://localhost:8000/v1", "http://localhost:8000/v1"),
            ("http://127.0.0.1:8000/v1", "http://127.0.0.1:8000/v1"),
            ("http://[::1]:8000/v1", "http://[::1]:8000/v1"),
        ],
    )
    def test_validate_llm_base_url_accepts_valid(self, url, expected):
        assert validate_llm_base_url(url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            None,
            "",
            "   ",
            "not a url",
            "openrouter.ai/api/v1",
            "https://",
            "ftp://host/v1",
            "http://evil.example/v1",
            "https://user:pass@evil.example/v1",
        ],
    )
    def test_validate_llm_base_url_rejects_invalid(self, url):
        with pytest.raises(SettingsError):
            validate_llm_base_url(url)


class TestIsLoopbackHost:
    def test_loopback_host(self):
        assert is_loopback_host("localhost")
        assert is_loopback_host("127.0.0.1")
        assert is_loopback_host("127.5.5.5")
        assert is_loopback_host("::1")
        assert not is_loopback_host("evil.example")
