from pathlib import Path


DOCKERFILE_PATH = Path(__file__).resolve().parents[1] / "Dockerfile"


def _dockerfile() -> str:
    return DOCKERFILE_PATH.read_text()


class TestDockerfileDeployerImage:
    def test_docker_cli_defaults_live_in_the_global_arg_scope(self):
        global_args = _dockerfile().split("FROM ", 1)[0]

        assert "ARG DOCKER_CLI_VERSION=" in global_args
        assert "ARG DOCKER_COMPOSE_VERSION=" in global_args

    def test_copies_the_docker_binary_not_the_extracted_directory(self):
        assert "COPY --from=builder /tmp/docker/docker /usr/local/bin/docker" in _dockerfile()

    def test_asserts_the_installed_cli_versions(self):
        dockerfile = _dockerfile()

        assert 'docker --version | grep -qF "${DOCKER_CLI_VERSION}"' in dockerfile
        assert 'docker compose version | grep -qF "${DOCKER_COMPOSE_VERSION}"' in dockerfile

    def test_installs_the_compose_plugin_in_a_cli_plugins_directory(self):
        assert "COPY --from=builder /tmp/docker-cli-plugins /usr/local/lib/docker/cli-plugins" in _dockerfile()

    def test_bakes_a_go_w_module_root_for_the_privileged_deployer(self):
        dockerfile = _dockerfile()

        assert "COPY demetra/ /opt/demetra/src/demetra/" in dockerfile
        assert "chmod -R go-w /opt/demetra/src" in dockerfile
