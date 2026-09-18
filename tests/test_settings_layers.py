from unittest.mock import patch

import pytest
from pydantic import SecretStr

from demetra.library.models import SessionEnvironment
from demetra.services.llm.factory import build_llm


OPENROUTER_SETTINGS = {
    "api_key": "settings-key",
    "model": "settings/model",
    "base_url": "https://openrouter.example/v1",
}


class TestBuildLlmEnvLayers:
    @pytest.mark.asyncio
    async def test_wires_resolved_environment_into_model(self):
        environment = SessionEnvironment(
            project_environment={"OPENROUTER_MODEL": "project/model"},
            user_environment={"OPENROUTER_API_KEY": "user-key"},
        )

        with patch("demetra.settings.OPENROUTER", OPENROUTER_SETTINGS):
            llm = await build_llm(temperature=0.1, max_tokens=10, environment=environment)

        assert llm.model_name == "project/model"
        api_key = llm.openai_api_key
        assert isinstance(api_key, SecretStr)
        assert api_key.get_secret_value() == "user-key"

    @pytest.mark.asyncio
    async def test_project_layer_wins_over_user_layer(self):
        environment = SessionEnvironment(
            project_environment={"OPENROUTER_MODEL": "project/model"},
            user_environment={"OPENROUTER_MODEL": "user/model"},
        )

        with patch("demetra.settings.OPENROUTER", OPENROUTER_SETTINGS):
            llm = await build_llm(temperature=0.1, max_tokens=10, environment=environment)

        assert llm.model_name == "project/model"

    @pytest.mark.asyncio
    async def test_falls_back_to_settings_when_environment_omitted(self):
        with patch("demetra.settings.OPENROUTER", OPENROUTER_SETTINGS):
            llm = await build_llm(temperature=0.1, max_tokens=10)

        assert llm.model_name == OPENROUTER_SETTINGS["model"]
        api_key = llm.openai_api_key
        assert isinstance(api_key, SecretStr)
        assert api_key.get_secret_value() == OPENROUTER_SETTINGS["api_key"]

    @pytest.mark.asyncio
    async def test_base_url_always_comes_from_settings(self):
        environment = SessionEnvironment(
            project_environment={"OPENROUTER_BASE_URL": "https://project.example"},
            user_environment={},
        )

        with patch("demetra.settings.OPENROUTER", OPENROUTER_SETTINGS):
            llm = await build_llm(temperature=0.1, max_tokens=10, environment=environment)

        assert str(llm.openai_api_base) == OPENROUTER_SETTINGS["base_url"]
