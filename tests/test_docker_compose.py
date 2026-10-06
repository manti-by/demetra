from pathlib import Path
from typing import Any

import yaml


COMPOSE_PATH = Path(__file__).resolve().parents[1] / "docker-compose.yaml"
LANGSMITH_ENV_DEFAULTS: dict[str, str] = {
    "LANGSMITH_TRACING": "true",
    "LANGSMITH_ENDPOINT": "https://api.smith.langchain.com",
    "LANGSMITH_API_KEY": "",
    "LANGSMITH_PROJECT": "Demetra",
}
OPENCODE_SERVICES = ("api", "worker", "watcher", "listener")


def _load_compose() -> dict[str, Any]:
    return yaml.safe_load(COMPOSE_PATH.read_text())


def _expected_interpolation(key: str) -> str:
    return f"${{{key}:-{LANGSMITH_ENV_DEFAULTS[key]}}}"


class TestDockerComposeLangSmithEnv:
    def test_langsmith_keys_interpolated_from_host(self):
        env_anchor = _load_compose()["x-demetra-env"]

        for key, default in LANGSMITH_ENV_DEFAULTS.items():
            assert env_anchor[key] == f"${{{key}:-{default}}}"

    def test_langsmith_keys_keep_existing_env_anchor_entries(self):
        env_anchor = _load_compose()["x-demetra-env"]

        assert env_anchor["DB_HOST"] == "postgres"
        assert env_anchor["REDIS_URL"] == "redis://redis:6379/1"

    def test_opencode_services_merge_the_env_anchor(self):
        compose = _load_compose()

        for service_name in OPENCODE_SERVICES:
            environment = compose["services"][service_name]["environment"]
            for key in LANGSMITH_ENV_DEFAULTS:
                assert environment[key] == _expected_interpolation(key)
