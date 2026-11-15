from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from demetra.deploy_lock import parse_command
from demetra.services.daemons.deploy_lock import (
    REDIS_OK,
    acquire_manual_deploy_lock,
    manual_deploy_timeout,
    redis_cli_command,
    redis_database,
    release_manual_deploy_lock,
)
from demetra.services.daemons.deployer import DEPLOY_LOCK_NAME, deploy_lock_timeout
from demetra.settings import DEPLOY, SUBPROCESS_TIMEOUT


class TestParseCommand:
    def test_strips_the_module_argument_separator(self):
        assert parse_command(arguments=["--", "make", "deploy-steps"]) == ["make", "deploy-steps"]

    def test_keeps_a_command_without_a_separator(self):
        assert parse_command(arguments=["make", "deploy-steps"]) == ["make", "deploy-steps"]

    def test_returns_nothing_for_an_empty_argv(self):
        assert parse_command(arguments=[]) == []

    def test_returns_nothing_for_a_lone_separator(self):
        assert parse_command(arguments=["--"]) == []


class TestRedisDatabase:
    def test_reads_the_index_from_the_url(self):
        assert redis_database("redis://redis:6379/1") == 1

    def test_defaults_to_zero_without_an_index(self):
        assert redis_database("redis://redis:6379") == 0

    def test_defaults_to_zero_for_a_non_numeric_index(self):
        assert redis_database("redis://redis:6379/not-a-db") == 0


class TestRedisCliCommand:
    def test_runs_redis_cli_inside_the_redis_container(self):
        command = redis_cli_command(Path("/srv/checkout"), "PING")

        assert command[1:3] == ["compose", "--project-directory"]
        assert command[command.index("exec") + 1] == "-T"
        assert command[command.index("exec") + 2] == "redis"
        assert command[command.index("redis-cli") + 1] == "-n"
        assert command[-1] == "PING"

    def test_names_the_checkout_env_file(self):
        command = redis_cli_command(Path("/srv/checkout"), "PING")

        assert command[command.index("--env-file") + 1] == str(Path("/srv/checkout/.env.docker"))

    def test_uses_the_deploy_lock_name(self):
        command = redis_cli_command(Path("/srv/checkout"), "SET", DEPLOY_LOCK_NAME, "token")

        assert DEPLOY_LOCK_NAME in command


class TestAcquireManualDeployLock:
    @pytest.mark.asyncio
    async def test_returns_the_token_when_the_key_was_set(self):
        with patch("demetra.services.daemons.deploy_lock.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, REDIS_OK, "")
            token = await acquire_manual_deploy_lock(checkout_path=Path("/srv/checkout"))

        assert token
        command = mock_run.call_args.kwargs["command"]
        assert command[command.index("SET") + 1] == DEPLOY_LOCK_NAME
        assert "NX" in command
        assert command[command.index("PX") + 1] == str(deploy_lock_timeout(checkout_path=Path("/srv/checkout")) * 1000)

    @pytest.mark.asyncio
    async def test_returns_none_when_the_lock_is_held(self):
        with patch("demetra.services.daemons.deploy_lock.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "", "")
            assert await acquire_manual_deploy_lock(checkout_path=Path("/srv/checkout")) is None

    @pytest.mark.asyncio
    async def test_returns_none_when_redis_is_unreachable(self):
        with patch("demetra.services.daemons.deploy_lock.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "service redis is not running")
            assert await acquire_manual_deploy_lock(checkout_path=Path("/srv/checkout")) is None


class TestReleaseManualDeployLock:
    @pytest.mark.asyncio
    async def test_deletes_the_key_only_when_the_token_matches(self):
        with patch("demetra.services.daemons.deploy_lock.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "1", "")
            await release_manual_deploy_lock(checkout_path=Path("/srv/checkout"), token="token")

        command = mock_run.call_args.kwargs["command"]
        assert command[command.index("EVAL") + 1].startswith("if redis.call('get'")
        assert "token" in command

    @pytest.mark.asyncio
    async def test_logs_a_failed_release(self):
        with patch("demetra.services.daemons.deploy_lock.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "boom")
            await release_manual_deploy_lock(checkout_path=Path("/srv/checkout"), token="token")

        assert mock_run.await_count == 1


class TestManualDeployTimeout:
    def test_stops_the_wrapped_command_before_the_lease_expires(self):
        assert manual_deploy_timeout(checkout_path=Path("/srv/checkout")) < deploy_lock_timeout(
            checkout_path=Path("/srv/checkout")
        )

    def test_leaves_the_manual_recipes_unused_drain_budget_as_slack(self):
        expected = deploy_lock_timeout(checkout_path=Path("/srv/checkout")) - DEPLOY["drain_timeout"]
        assert manual_deploy_timeout(checkout_path=Path("/srv/checkout")) == expected


class TestWorkerStopGracePeriod:
    def test_covers_the_queue_job_timeout(self):
        compose = yaml.safe_load((Path(__file__).resolve().parents[1] / "docker-compose.yaml").read_text())
        grace = str(compose["services"]["worker"]["stop_grace_period"]).split(":-")[-1].rstrip("}")

        assert grace.endswith("s")
        assert int(grace.removesuffix("s")) >= SUBPROCESS_TIMEOUT + 60

    def test_the_up_step_outlives_the_grace_period(self):
        compose = yaml.safe_load((Path(__file__).resolve().parents[1] / "docker-compose.yaml").read_text())
        grace = str(compose["services"]["worker"]["stop_grace_period"]).split(":-")[-1].rstrip("}")

        assert DEPLOY["step_timeout"] > int(grace.removesuffix("s"))
