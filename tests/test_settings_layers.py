from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr

from demetra.services.linear import get_linear_config_value
from demetra.services.llm.factory import build_llm


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
    async def test_unknown_name_returns_none(self, linear_full_settings):
        with (
            patch("demetra.services.linear.LINEAR", linear_full_settings),
            patch("demetra.services.linear.get_user_environments_decrypted", new_callable=AsyncMock, return_value={}),
        ):
            result = await get_linear_config_value(name="unknown_key", user_id="user-1")

        assert result is None


class TestBuildLlmEnvLayers:
    def test_uses_user_env_model_and_api_key(self):
        llm = build_llm(
            temperature=0.1,
            max_tokens=10,
            user_environment={"OPENROUTER_MODEL": "user/model", "OPENROUTER_API_KEY": "user-key"},
        )

        assert llm.model_name == "user/model"
        api_key = llm.openai_api_key
        assert isinstance(api_key, SecretStr)
        assert api_key.get_secret_value() == "user-key"

    def test_falls_back_to_settings(self):
        settings = {"api_key": "settings-key", "model": "settings/model", "base_url": "https://example.com/v1"}
        with patch("demetra.services.llm.factory.OPENROUTER", settings):
            llm = build_llm(temperature=0.1, max_tokens=10)

        assert llm.model_name == "settings/model"
        api_key = llm.openai_api_key
        assert isinstance(api_key, SecretStr)
        assert api_key.get_secret_value() == "settings-key"
