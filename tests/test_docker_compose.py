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


class TestDockerComposeDeployerService:
    def test_deployer_runs_the_daemon_entrypoint(self):
        deployer = _load_compose()["services"]["deployer"]

        assert deployer["command"] == ["python", "-m", "demetra.deployer"]

    def test_deployer_runs_as_root_without_the_privilege_drop_entrypoint(self):
        deployer = _load_compose()["services"]["deployer"]

        assert deployer["user"] == "root"
        assert deployer["entrypoint"] == ""

    def test_deployer_shares_the_host_pid_namespace_for_the_nginx_reload(self):
        deployer = _load_compose()["services"]["deployer"]

        assert deployer["pid"] == "host"

    def test_deployer_can_enter_the_host_namespaces_for_the_nginx_reload(self):
        deployer = _load_compose()["services"]["deployer"]

        assert "SYS_ADMIN" in deployer["cap_add"]

    def test_deployer_keeps_its_state_in_its_own_volume(self):
        compose = _load_compose()
        deployer = compose["services"]["deployer"]

        assert "demetra_deployer_data:/var/lib/demetra/" in deployer["volumes"]
        assert "demetra_deployer_data" in compose["volumes"]

    def test_deployer_does_not_mount_the_app_home_volume(self):
        deployer = _load_compose()["services"]["deployer"]

        assert not any(volume.startswith("demetra_app_data:") for volume in deployer["volumes"])

    def test_deployer_mounts_the_docker_socket(self):
        deployer = _load_compose()["services"]["deployer"]

        assert "/var/run/docker.sock:/var/run/docker.sock" in deployer["volumes"]

    def test_deployer_mounts_the_host_checkout_at_the_same_path(self):
        deployer = _load_compose()["services"]["deployer"]
        checkout = "${DEPLOY_HOST_CHECKOUT:-/home/manti/www/demetra}"

        assert f"{checkout}:{checkout}" in deployer["volumes"]

    def test_deployer_uses_the_host_checkout_from_the_environment(self):
        deployer = _load_compose()["services"]["deployer"]

        assert deployer["environment"]["DEPLOY_HOST_CHECKOUT"] == "${DEPLOY_HOST_CHECKOUT:-/home/manti/www/demetra}"

    def test_deployer_runs_from_the_image_owned_module_root(self):
        deployer = _load_compose()["services"]["deployer"]

        assert deployer["working_dir"] == "/opt/demetra/src"

    def test_deployer_waits_for_redis(self):
        deployer = _load_compose()["services"]["deployer"]

        assert deployer["depends_on"]["redis"]["condition"] == "service_healthy"

    def test_redis_is_not_published_to_the_host(self):
        assert "ports" not in _load_compose()["services"]["redis"]
