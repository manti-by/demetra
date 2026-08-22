from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr

from demetra.services.linear import get_linear_config_value
from demetra.services.llm.config import get_openrouter_config
from demetra.services.llm.factory import build_llm


@pytest.fixture
def openrouter_settings() -> dict:
    return {
        "api_key": "settings-key",
        "model": "settings/model",
        "base_url": "https://openrouter.example/v1",
    }


class TestGetLinearConfigValue:
    @pytest.mark.asyncio
    async def test_reads_state_override_from_user_environment(self, linear_full_settings):
        user_environment = {"LINEAR_STATE_TODO_ID": "user-todo-state"}
        with (
            patch("demetra.services.linear.LINEAR", linear_full_settings),
            patch(
                "demetra.services.linear.get_user_environments_decrypted",
                new_callable=AsyncMock,
                return_value=user_environment,
            ),
        ):
            result = await get_linear_config_value(name="todo", user_id="user-1")

        assert result == "user-todo-state"

    @pytest.mark.asyncio
    async def test_falls_back_to_settings_when_state_missing_from_user_env(self, linear_full_settings):
        with (
            patch("demetra.services.linear.LINEAR", linear_full_settings),
            patch("demetra.services.linear.get_user_environments_decrypted", new_callable=AsyncMock, return_value={}),
        ):
            result = await get_linear_config_value(name="todo", user_id="user-1")

        assert result == linear_full_settings["states"]["todo"]

    @pytest.mark.asyncio
    async def test_reads_team_id_from_user_environment(self, linear_full_settings):
        with (
            patch("demetra.services.linear.LINEAR", linear_full_settings),
            patch(
                "demetra.services.linear.get_user_environments_decrypted",
                new_callable=AsyncMock,
                return_value={"LINEAR_TEAM_ID": "user-team"},
            ),
        ):
            result = await get_linear_config_value(name="team_id", user_id="user-1")

        assert result == "user-team"

    @pytest.mark.asyncio
    async def test_reads_default_state_from_user_environment(self, linear_full_settings):
        with (
            patch("demetra.services.linear.LINEAR", linear_full_settings),
            patch(
                "demetra.services.linear.get_user_environments_decrypted",
                new_callable=AsyncMock,
                return_value={"LINEAR_DEFAULT_STATE_ID": "user-default-state"},
            ),
        ):
            result = await get_linear_config_value(name="default_state", user_id="user-1")

        assert result == "user-default-state"

    @pytest.mark.asyncio
    async def test_skips_db_when_user_id_is_none(self, linear_full_settings):
        with (
            patch("demetra.services.linear.LINEAR", linear_full_settings),
            patch(
                "demetra.services.linear.get_user_environments_decrypted", new_callable=AsyncMock
            ) as mock_get_user_env,
        ):
            result = await get_linear_config_value(name="todo")

        assert result == linear_full_settings["states"]["todo"]
        mock_get_user_env.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_settings_when_env_values_are_empty(self, openrouter_settings):
        with (
            patch("demetra.services.llm.OPENROUTER", openrouter_settings),
            patch(
                "demetra.services.llm.get_user_environments_decrypted",
                new_callable=AsyncMock,
                return_value={"OPENROUTER_MODEL": "", "OPENROUTER_API_KEY": ""},
            ),
        ):
            result = await get_openrouter_config(user_id="user-1")

        assert result["model"] == openrouter_settings["model"]
        assert result["api_key"] == openrouter_settings["api_key"]

    @pytest.mark.asyncio
    async def test_unknown_name_returns_none(self, linear_full_settings):
        with (
            patch("demetra.services.linear.LINEAR", linear_full_settings),
            patch("demetra.services.linear.get_user_environments_decrypted", new_callable=AsyncMock, return_value={}),
        ):
            result = await get_linear_config_value(name="unknown_key", user_id="user-1")

        assert result is None


class TestGetOpenRouterConfig:
    @pytest.mark.asyncio
    async def test_reads_model_override_from_user_environment(self, openrouter_settings):
        with (
            patch("demetra.services.llm.OPENROUTER", openrouter_settings),
            patch(
                "demetra.services.llm.get_user_environments_decrypted",
                new_callable=AsyncMock,
                return_value={"OPENROUTER_MODEL": "user/model"},
            ),
        ):
            result = await get_openrouter_config(user_id="user-1")

        assert result["model"] == "user/model"

    @pytest.mark.asyncio
    async def test_reads_api_key_override_from_user_environment(self, openrouter_settings):
        with (
            patch("demetra.services.llm.OPENROUTER", openrouter_settings),
            patch(
                "demetra.services.llm.get_user_environments_decrypted",
                new_callable=AsyncMock,
                return_value={"OPENROUTER_API_KEY": "user-key"},
            ),
        ):
            result = await get_openrouter_config(user_id="user-1")

        assert result["api_key"] == "user-key"

    @pytest.mark.asyncio
    async def test_falls_back_to_settings_when_keys_missing_from_user_env(self, openrouter_settings):
        with (
            patch("demetra.services.llm.OPENROUTER", openrouter_settings),
            patch("demetra.services.llm.get_user_environments_decrypted", new_callable=AsyncMock, return_value={}),
        ):
            result = await get_openrouter_config(user_id="user-1")

        assert result == openrouter_settings

    @pytest.mark.asyncio
    async def test_skips_db_when_user_id_is_none(self, openrouter_settings):
        with (
            patch("demetra.services.llm.OPENROUTER", openrouter_settings),
            patch("demetra.services.llm.get_user_environments_decrypted", new_callable=AsyncMock) as mock_get_user_env,
        ):
            result = await get_openrouter_config()

        assert result == openrouter_settings
        mock_get_user_env.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_base_url_always_comes_from_settings(self, openrouter_settings):
        with (
            patch("demetra.services.llm.OPENROUTER", openrouter_settings),
            patch(
                "demetra.services.llm.get_user_environments_decrypted",
                new_callable=AsyncMock,
                return_value={"OPENROUTER_MODEL": "user/model", "OPENROUTER_API_KEY": "user-key"},
            ),
        ):
            result = await get_openrouter_config(user_id="user-1")

        assert result["base_url"] == openrouter_settings["base_url"]


class TestBuildLlmEnvLayers:
    @pytest.mark.asyncio
    async def test_wires_resolved_config_into_model(self, openrouter_settings):
        resolved = {
            "api_key": "user-key",
            "model": "user/model",
            "base_url": openrouter_settings["base_url"],
        }
        with patch("demetra.services.llm.factory.get_openrouter_config", new_callable=AsyncMock) as mock_config:
            mock_config.return_value = resolved
            llm = await build_llm(temperature=0.1, max_tokens=10, user_id="user-1")

        mock_config.assert_awaited_once_with(user_id="user-1")
        assert llm.model_name == "user/model"
        api_key = llm.openai_api_key
        assert isinstance(api_key, SecretStr)
        assert api_key.get_secret_value() == "user-key"
