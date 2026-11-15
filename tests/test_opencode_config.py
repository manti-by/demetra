import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
OPENCODE_CONFIG_PATH = REPO_ROOT / "opencode.json"
COMPOSE_PATH = REPO_ROOT / "docker-compose.yaml"
DERIVE_SCRIPT_PATH = REPO_ROOT / "configs" / "derive-opencode-config.py"
LINEAR_ENDPOINT = "https://mcp.linear.app/mcp"


def _load_opencode_config() -> dict[str, Any]:
    return json.loads(OPENCODE_CONFIG_PATH.read_text(encoding="utf-8"))


def _load_derive_module():
    spec = importlib.util.spec_from_file_location("derive_opencode_config", DERIVE_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {DERIVE_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestLinearMcpAuthentication:
    def test_uses_the_full_read_write_endpoint(self):
        config = _load_opencode_config()

        assert config["mcp"]["servers"]["Linear"]["url"] == LINEAR_ENDPOINT

    def test_disables_the_oauth_round_trip(self):
        config = _load_opencode_config()

        assert config["mcp"]["servers"]["Linear"]["oauth"] is False

    def test_sends_a_static_bearer_header_from_the_environment(self):
        config = _load_opencode_config()

        assert config["mcp"]["servers"]["Linear"]["headers"] == {"Authorization": "Bearer {env:LINEAR_API_KEY}"}

    def test_no_key_material_is_inlined(self):
        config = _load_opencode_config()

        assert "lin_api_" not in json.dumps(config)


class TestDemetraMcpCommand:
    def test_does_not_reference_a_working_directory_env_file(self):
        config = _load_opencode_config()

        assert "--env-file" not in config["mcp"]["servers"]["Demetra"]["command"]

    def test_runs_the_module_through_uv(self):
        config = _load_opencode_config()

        assert config["mcp"]["servers"]["Demetra"]["command"] == [
            "uv",
            "run",
            "python",
            "-m",
            "demetra.mcp_server",
        ]


class TestDeriveOpencodeConfig:
    def test_keeps_only_the_schema_and_provider(self, tmp_path):
        module = _load_derive_module()
        source = tmp_path / "host.json"
        source.write_text(
            json.dumps(
                {
                    "$schema": "https://opencode.ai/config.json",
                    "provider": {"minimax": {"npm": "@ai-sdk/openai-compatible"}},
                    "mcp": {"servers": {"Linear": {"oauth": {}}}},
                    "plugins": ["some-plugin"],
                }
            ),
            encoding="utf-8",
        )

        config = module.derive_config(source=source)

        assert config == {
            "$schema": "https://opencode.ai/config.json",
            "provider": {"minimax": {"npm": "@ai-sdk/openai-compatible"}},
        }

    def test_rejects_a_non_object_document(self, tmp_path):
        module = _load_derive_module()
        source = tmp_path / "host.json"
        source.write_text("[]", encoding="utf-8")

        with pytest.raises(ValueError, match="JSON object"):
            module.derive_config(source=source)

    def test_rejects_a_non_object_provider(self, tmp_path):
        module = _load_derive_module()
        source = tmp_path / "host.json"
        source.write_text('{"provider": []}', encoding="utf-8")

        with pytest.raises(ValueError, match="non-object 'provider'"):
            module.derive_config(source=source)

    def test_writes_an_owner_only_config(self, tmp_path):
        module = _load_derive_module()
        target = tmp_path / "nested" / "opencode.json"

        module.write_config(
            config={"$schema": "https://opencode.ai/config.json", "provider": {"p": {}}},
            target=target,
        )

        assert json.loads(target.read_text(encoding="utf-8"))["provider"] == {"p": {}}
        assert target.stat().st_mode & 0o777 == 0o600

    def test_cli_derives_the_container_config(self, tmp_path):
        source = tmp_path / "providers.json"
        target = tmp_path / "opencode.json"
        source.write_text(
            json.dumps({"$schema": "https://opencode.ai/config.json", "provider": {"p": {}}, "mcp": {}}),
            encoding="utf-8",
        )

        subprocess.run(
            [sys.executable, str(DERIVE_SCRIPT_PATH), str(source), str(target)],
            check=True,
            capture_output=True,
            text=True,
        )

        assert json.loads(target.read_text(encoding="utf-8")) == {
            "$schema": "https://opencode.ai/config.json",
            "provider": {"p": {}},
        }


class TestDockerProviderCredentialsMount:
    def test_host_config_is_mounted_as_providers_only(self):
        compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
        volumes = compose["x-demetra-app"]["volumes"]

        assert ".keys/opencode/opencode.json:/home/demetra/.config/opencode/providers.json:ro" in volumes

    def test_nothing_mounts_over_the_global_config(self):
        compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
        volumes = compose["x-demetra-app"]["volumes"]

        assert not any(volume.endswith(":/home/demetra/.config/opencode/opencode.json") for volume in volumes)

    def test_entrypoint_derives_the_global_config(self):
        entrypoint = (REPO_ROOT / "configs" / "docker-entrypoint.sh").read_text(encoding="utf-8")

        assert "derive-opencode-config.py" in entrypoint
        assert "providers.json" in entrypoint
        assert "/home/demetra/.config/opencode/opencode.json" in entrypoint
