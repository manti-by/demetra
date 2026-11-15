import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from demetra.library.models import DeployState
from demetra.services.daemons.deployer import (
    CI_STATUS_FAILED,
    CI_STATUS_PASSED,
    CI_STATUS_PENDING,
    CI_STATUS_UNKNOWN,
    DEPLOY_IMAGE,
    DOCKER_SOCKET,
    IMAGE_REVISION_LABEL,
    NO_LABEL_VALUE,
    acquire_deploy_lock,
    build_deploy_steps,
    checkout_has_no_local_changes,
    checkout_matches_sha,
    checkout_owner_prefix,
    combine_check_run_pages,
    default_state_path,
    deploy_lock_timeout,
    get_checkout_head_sha,
    get_ci_status,
    get_origin_repository,
    get_remote_master_sha,
    get_running_revision,
    is_queue_drained,
    load_state,
    parse_remote_sha,
    parse_repository_slug,
    recreate_deployer,
    recreate_deployer_command,
    run_deploy,
    run_deploy_cycle,
    run_deploy_step,
    save_state,
    should_deploy,
    summarize_check_runs,
    wait_for_queue_drain,
)
from demetra.settings import DEPLOY


SHA = "a" * 40
OTHER_SHA = "b" * 40


def _mock_queue(*, waiting: int = 0, started: list | None = None) -> MagicMock:
    mock_queue = MagicMock()
    mock_queue.count = waiting
    mock_queue.started_job_registry.get_job_ids.return_value = started or []
    return mock_queue


class TestParseRemoteSha:
    def test_parses_the_first_column(self):
        assert parse_remote_sha(f"{SHA}\trefs/heads/master") == SHA

    def test_returns_none_for_empty_output(self):
        assert parse_remote_sha("") is None
        assert parse_remote_sha("   \n") is None


class TestParseRepositorySlug:
    def test_parses_https_remote(self):
        assert parse_repository_slug("https://github.com/manti-by/demetra.git") == "manti-by/demetra"

    def test_parses_ssh_remote(self):
        assert parse_repository_slug("git@github.com:manti-by/demetra.git") == "manti-by/demetra"

    def test_parses_remote_without_suffix(self):
        assert parse_repository_slug("https://github.com/manti-by/demetra") == "manti-by/demetra"

    def test_returns_none_for_empty_url(self):
        assert parse_repository_slug("") is None


class TestGetRemoteMasterSha:
    @pytest.mark.asyncio
    async def test_returns_the_remote_commit(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, f"{SHA}\trefs/heads/master", "")
            result = await get_remote_master_sha(checkout_path=Path("/tmp/checkout"))
        assert result == SHA

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "fatal: unable to access")
            result = await get_remote_master_sha(checkout_path=Path("/tmp/checkout"))
        assert result is None


class TestGetCheckoutHeadSha:
    @pytest.mark.asyncio
    async def test_returns_the_checked_out_commit(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, f"{SHA}\n", "")
            result = await get_checkout_head_sha(checkout_path=Path("/tmp/checkout"))
        assert result == SHA

    @pytest.mark.asyncio
    async def test_bounds_the_read_by_the_step_timeout(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, f"{SHA}\n", "")
            await get_checkout_head_sha(checkout_path=Path("/tmp/checkout"))
        assert mock_run.call_args.kwargs["timeout"] == DEPLOY["step_timeout"]

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (128, "", "fatal: not a git repository")
            result = await get_checkout_head_sha(checkout_path=Path("/tmp/checkout"))
        assert result is None


class TestGetRunningRevision:
    @pytest.mark.asyncio
    async def test_resolves_this_stacks_api_container_through_compose(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [(0, "abc123\n", ""), (0, f"{SHA}\n", "")]
            result = await get_running_revision(checkout_path=Path("/tmp/checkout"))

        assert result == SHA
        ps_command = mock_run.call_args_list[0].kwargs["command"]
        assert ps_command[1:3] == ["compose", "--project-directory"]
        assert ps_command[ps_command.index("--project-directory") + 1] == "/tmp/checkout"
        assert ps_command[-3:] == ["ps", "-q", "api"]
        assert ps_command[ps_command.index("--env-file") + 1] == str(Path("/tmp/checkout/.env.docker"))
        inspect_command = mock_run.call_args_list[1].kwargs["command"]
        assert IMAGE_REVISION_LABEL in inspect_command[inspect_command.index("--format") + 1]
        assert inspect_command[-1] == "abc123"

    @pytest.mark.asyncio
    async def test_returns_none_without_a_labelled_container(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "\n", "")
            assert await get_running_revision(checkout_path=Path("/tmp/checkout")) is None

    @pytest.mark.asyncio
    async def test_returns_none_when_the_label_is_absent(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [(0, "abc123\n", ""), (0, f"{NO_LABEL_VALUE}\n", "")]
            assert await get_running_revision(checkout_path=Path("/tmp/checkout")) is None

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "Cannot connect to the Docker daemon")
            assert await get_running_revision(checkout_path=Path("/tmp/checkout")) is None


class TestCheckoutHasNoLocalChanges:
    @pytest.mark.asyncio
    async def test_true_for_a_clean_working_tree(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "", "")
            assert await checkout_has_no_local_changes(checkout_path=Path("/tmp/checkout")) is True

    @pytest.mark.asyncio
    async def test_false_when_a_tracked_file_is_modified(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, " M demetra/settings.py\n", "")
            assert await checkout_has_no_local_changes(checkout_path=Path("/tmp/checkout")) is False

    @pytest.mark.asyncio
    async def test_false_when_an_untracked_file_would_ship(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "?? demetra/patch.py\n", "")
            assert await checkout_has_no_local_changes(checkout_path=Path("/tmp/checkout")) is False

    @pytest.mark.asyncio
    async def test_reads_the_status_without_listing_ignored_files(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "", "")
            await checkout_has_no_local_changes(checkout_path=Path("/tmp/checkout"))
        assert "--ignored" not in mock_run.call_args.kwargs["command"]

    @pytest.mark.asyncio
    async def test_false_when_the_status_cannot_be_read(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (128, "", "fatal: not a git repository")
            assert await checkout_has_no_local_changes(checkout_path=Path("/tmp/checkout")) is False


class TestGetOriginRepository:
    @pytest.mark.asyncio
    async def test_resolves_the_origin_slug(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "https://github.com/manti-by/demetra.git\n", "")
            result = await get_origin_repository(checkout_path=Path("/tmp/checkout"))
        assert result == "manti-by/demetra"

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "error: No such remote 'origin'")
            result = await get_origin_repository(checkout_path=Path("/tmp/checkout"))
        assert result is None


class TestSummarizeCheckRuns:
    def test_pending_without_check_runs(self):
        assert summarize_check_runs(payload={"total_count": 0, "check_runs": []}) == CI_STATUS_PENDING

    def test_pending_while_a_run_is_not_completed(self):
        payload = {
            "check_runs": [
                {"status": "completed", "conclusion": "success"},
                {"status": "in_progress", "conclusion": None},
            ]
        }
        assert summarize_check_runs(payload=payload) == CI_STATUS_PENDING

    def test_failed_when_a_run_failed(self):
        payload = {"check_runs": [{"status": "completed", "conclusion": "failure"}]}
        assert summarize_check_runs(payload=payload) == CI_STATUS_FAILED

    def test_passed_when_every_run_succeeded(self):
        payload = {"check_runs": [{"status": "completed", "conclusion": "success"}]}
        assert summarize_check_runs(payload=payload) == CI_STATUS_PASSED

    def test_neutral_and_skipped_count_as_success(self):
        payload = {
            "check_runs": [
                {"status": "completed", "conclusion": "neutral"},
                {"status": "completed", "conclusion": "skipped"},
                {"status": "completed", "conclusion": "success"},
            ]
        }
        assert summarize_check_runs(payload=payload) == CI_STATUS_PASSED


class TestGetCiStatus:
    @pytest.mark.asyncio
    async def test_reads_the_check_runs(self):
        payload = {"check_runs": [{"status": "completed", "conclusion": "success"}]}
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, json.dumps(payload), "")
            result = await get_ci_status(sha=SHA, repository="manti-by/demetra")
        assert result == CI_STATUS_PASSED

    @pytest.mark.asyncio
    async def test_reads_every_page_of_check_runs(self):
        first_page = {"check_runs": [{"status": "completed", "conclusion": "success"}]}
        second_page = {"check_runs": [{"status": "completed", "conclusion": "failure"}]}
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, json.dumps([first_page, second_page]), "")
            result = await get_ci_status(sha=SHA, repository="manti-by/demetra")
        assert result == CI_STATUS_FAILED
        command = mock_run.call_args.kwargs["command"]
        assert "--paginate" in command
        assert "--slurp" in command

    @pytest.mark.asyncio
    async def test_reports_unknown_when_the_api_call_fails(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "HTTP 404")
            result = await get_ci_status(sha=SHA, repository="manti-by/demetra")
        assert result == CI_STATUS_UNKNOWN

    @pytest.mark.asyncio
    async def test_reports_unknown_on_unparsable_output(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "not json", "")
            result = await get_ci_status(sha=SHA, repository="manti-by/demetra")
        assert result == CI_STATUS_UNKNOWN

    @pytest.mark.asyncio
    async def test_reports_unknown_for_a_non_object_payload(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "null", "")
            result = await get_ci_status(sha=SHA, repository="manti-by/demetra")
        assert result == CI_STATUS_UNKNOWN


class TestCombineCheckRunPages:
    def test_merges_the_runs_of_every_page(self):
        pages = [
            {"check_runs": [{"status": "completed", "conclusion": "success"}]},
            {"check_runs": [{"status": "in_progress", "conclusion": None}]},
        ]

        assert combine_check_run_pages(pages=pages) == {
            "check_runs": [
                {"status": "completed", "conclusion": "success"},
                {"status": "in_progress", "conclusion": None},
            ]
        }

    def test_skips_pages_that_are_not_objects(self):
        assert combine_check_run_pages(pages=[None, {"check_runs": []}]) == {"check_runs": []}


class TestIsQueueDrained:
    def test_false_with_a_waiting_job(self):
        with patch("demetra.services.daemons.deployer.queue", _mock_queue(waiting=1)):
            assert is_queue_drained() is False

    def test_false_with_a_running_job(self):
        with patch("demetra.services.daemons.deployer.queue", _mock_queue(started=["job-1"])):
            assert is_queue_drained() is False

    def test_true_without_waiting_or_running_jobs(self):
        with patch("demetra.services.daemons.deployer.queue", _mock_queue()):
            assert is_queue_drained() is True


class TestWaitForQueueDrain:
    @pytest.mark.asyncio
    async def test_returns_true_when_the_queue_drains(self):
        with patch("demetra.services.daemons.deployer.is_queue_drained", return_value=True):
            assert await wait_for_queue_drain(timeout=10) is True

    @pytest.mark.asyncio
    async def test_returns_false_on_timeout(self):
        with (
            patch("demetra.services.daemons.deployer.is_queue_drained", return_value=False),
            patch("demetra.services.daemons.deployer.asyncio.sleep", new_callable=AsyncMock),
        ):
            assert await wait_for_queue_drain(timeout=0) is False


class TestShouldDeploy:
    def test_false_for_the_deployed_commit(self):
        state = DeployState(last_deployed_sha=SHA)
        assert should_deploy(state=state, sha=SHA, now=state.last_deploy_at + DEPLOY["min_interval"]) is False

    def test_false_within_the_minimum_interval(self):
        state = DeployState(last_deployed_sha=OTHER_SHA, last_deploy_at=1000.0)
        assert should_deploy(state=state, sha=SHA, now=1000.0 + DEPLOY["min_interval"] - 1) is False

    def test_true_after_the_minimum_interval(self):
        state = DeployState(last_deployed_sha=OTHER_SHA, last_deploy_at=1000.0)
        assert should_deploy(state=state, sha=SHA, now=1000.0 + DEPLOY["min_interval"]) is True


class TestDeployState:
    def test_round_trips_through_the_state_file(self, tmp_path: Path):
        state_path = tmp_path / "nested" / "deployer-state.json"
        state = DeployState(last_deployed_sha=SHA, last_deploy_at=123.5, last_failed_sha=OTHER_SHA, last_error="x")

        save_state(path=state_path, state=state)

        assert load_state(path=state_path) == state

    def test_missing_file_is_an_empty_state(self, tmp_path: Path):
        assert load_state(path=tmp_path / "missing.json") == DeployState()

    def test_corrupt_file_is_an_empty_state(self, tmp_path: Path):
        state_path = tmp_path / "deployer-state.json"
        state_path.write_text("{not json")

        assert load_state(path=state_path) == DeployState()

    def test_coerces_a_malformed_timestamp(self):
        state = DeployState.from_payload({"last_deployed_sha": SHA, "last_deploy_at": "not a number"})

        assert state.last_deployed_sha == SHA
        assert state.last_deploy_at == 0.0

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
    def test_rejects_a_non_finite_timestamp(self, value):
        state = DeployState.from_payload({"last_deploy_at": value})

        assert state.last_deploy_at == 0.0

    def test_reads_the_pending_recreate_flag(self):
        assert DeployState.from_payload({"pending_recreate": True}).pending_recreate is True
        assert DeployState.from_payload({}).pending_recreate is False

    def test_a_non_object_payload_is_an_empty_state(self, tmp_path: Path):
        state_path = tmp_path / "deployer-state.json"
        state_path.write_text("null")

        assert load_state(path=state_path) == DeployState()

    def test_a_list_payload_is_an_empty_state(self, tmp_path: Path):
        state_path = tmp_path / "deployer-state.json"
        state_path.write_text("[]")

        assert load_state(path=state_path) == DeployState()


class TestDefaultStatePath:
    def test_uses_the_configured_path(self, monkeypatch):
        monkeypatch.setitem(DEPLOY, "state_path", Path("/custom/state.json"))

        assert default_state_path() == Path("/custom/state.json")

    def test_defaults_to_the_deployer_volume_not_the_app_home(self, monkeypatch):
        monkeypatch.setitem(DEPLOY, "state_path", None)

        state_path = default_state_path()

        assert state_path == Path("/var/lib/demetra/deployer-state.json")
        assert state_path.parent == Path("/var/lib/demetra")


class TestBuildDeploySteps:
    def test_pulls_builds_migrates_and_restarts_the_stack(self):
        steps = build_deploy_steps(checkout_path=Path("/srv/checkout"))
        names = [name for name, _ in steps]

        assert names == ["pull", "build", "pull_images", "migrate", "up", "nginx_reload"]

    def test_pull_is_fast_forward_only(self):
        pull = dict(build_deploy_steps(checkout_path=Path("/srv/checkout")))["pull"]

        assert pull[-2:] == ["pull", "--ff-only"]
        assert any(arg == f"safe.directory={Path('/srv/checkout')}" for arg in pull)

    def test_up_force_recreates_the_app_services_without_the_deployer(self):
        up = dict(build_deploy_steps(checkout_path=Path("/srv/checkout")))["up"]

        assert "--force-recreate" in up
        assert "--scale" in up
        assert list(DEPLOY["compose_services"]) == up[-5:]
        assert "deployer" not in up

    def test_uses_the_checkout_env_file(self):
        pull_images = dict(build_deploy_steps(checkout_path=Path("/srv/checkout")))["pull_images"]

        assert "--env-file" in pull_images
        assert str(Path("/srv/checkout/.env.docker")) in pull_images

    def test_names_the_checkout_as_the_compose_project_directory(self):
        pull_images = dict(build_deploy_steps(checkout_path=Path("/srv/checkout")))["pull_images"]

        assert pull_images[pull_images.index("--project-directory") + 1] == str(Path("/srv/checkout"))

    def test_builds_from_an_absolute_context(self):
        build = dict(build_deploy_steps(checkout_path=Path("/srv/checkout")))["build"]

        assert build[-1] == str(Path("/srv/checkout"))
        assert "." not in build

    def test_labels_the_image_with_the_gated_commit(self):
        build = dict(build_deploy_steps(checkout_path=Path("/srv/checkout"), sha=SHA))["build"]

        assert build[build.index("--label") + 1] == f"{IMAGE_REVISION_LABEL}={SHA}"

    def test_omits_the_label_without_a_gated_commit(self):
        build = dict(build_deploy_steps(checkout_path=Path("/srv/checkout")))["build"]

        assert "--label" not in build


class TestCheckoutOwnerPrefix:
    def test_drops_to_the_checkout_owner_when_running_as_root(self, tmp_path: Path):
        owner = tmp_path.stat()

        with patch("demetra.services.daemons.deployer.os.geteuid", return_value=0):
            prefix = checkout_owner_prefix(checkout_path=tmp_path)

        assert prefix == ["setpriv", f"--reuid={owner.st_uid}", f"--regid={owner.st_gid}", "--clear-groups"]

    def test_is_empty_for_a_non_root_daemon(self, tmp_path: Path):
        with patch("demetra.services.daemons.deployer.os.geteuid", return_value=1000):
            assert checkout_owner_prefix(checkout_path=tmp_path) == []

    def test_pull_runs_as_the_checkout_owner(self, tmp_path: Path):
        with patch("demetra.services.daemons.deployer.os.geteuid", return_value=0):
            pull = dict(build_deploy_steps(checkout_path=tmp_path))["pull"]

        assert pull[0] == "setpriv"
        assert "--clear-groups" in pull


class TestDeployLockTimeout:
    def test_covers_every_step_and_the_in_lock_drain_wait(self):
        steps = build_deploy_steps(checkout_path=Path("/srv/checkout"))

        expected = (len(steps) + 1) * DEPLOY["step_timeout"] + DEPLOY["drain_timeout"]
        assert deploy_lock_timeout(checkout_path=Path("/srv/checkout")) == expected

    def test_budgets_the_post_pull_head_read(self):
        steps = build_deploy_steps(checkout_path=Path("/srv/checkout"))

        assert deploy_lock_timeout(checkout_path=Path("/srv/checkout")) > len(steps) * DEPLOY["step_timeout"]


class TestAcquireDeployLock:
    def test_returns_none_when_another_deploy_holds_the_lock(self):
        with patch("demetra.services.daemons.deployer.connection") as mock_connection:
            mock_connection.lock.return_value.acquire.return_value = False
            assert acquire_deploy_lock(checkout_path=Path("/srv/checkout"), blocking=False) is None

    def test_uses_the_deploy_lock_name_and_ttl(self):
        with patch("demetra.services.daemons.deployer.connection") as mock_connection:
            mock_connection.lock.return_value.acquire.return_value = True
            lock = acquire_deploy_lock(checkout_path=Path("/srv/checkout"), blocking=True)

        assert lock is mock_connection.lock.return_value
        assert mock_connection.lock.call_args.args[0] == "demetra:deployer"
        assert mock_connection.lock.call_args.kwargs["timeout"] == deploy_lock_timeout(
            checkout_path=Path("/srv/checkout")
        )


class TestRunDeploy:
    @pytest.mark.asyncio
    async def test_runs_every_step_in_order(self):
        with (
            patch("demetra.services.daemons.deployer.run_deploy_step", new_callable=AsyncMock) as mock_step,
            patch("demetra.services.daemons.deployer.checkout_matches_sha", new_callable=AsyncMock) as mock_match,
            patch("demetra.services.daemons.deployer.wait_for_queue_drain", new_callable=AsyncMock) as mock_drain,
        ):
            mock_step.return_value = True
            mock_match.return_value = True
            mock_drain.return_value = True
            result = await run_deploy(checkout_path=Path("/srv/checkout"), sha=SHA)

        assert result is True
        names = [call.kwargs["name"] for call in mock_step.await_args_list]
        assert names == [name for name, _ in build_deploy_steps(checkout_path=Path("/srv/checkout"))]

    @pytest.mark.asyncio
    async def test_stops_at_the_first_required_failure(self):
        with (
            patch("demetra.services.daemons.deployer.run_deploy_step", new_callable=AsyncMock) as mock_step,
            patch("demetra.services.daemons.deployer.checkout_matches_sha", new_callable=AsyncMock) as mock_match,
            patch("demetra.services.daemons.deployer.wait_for_queue_drain", new_callable=AsyncMock) as mock_drain,
        ):
            mock_step.side_effect = [True, False]
            mock_match.return_value = True
            mock_drain.return_value = True
            result = await run_deploy(checkout_path=Path("/srv/checkout"), sha=SHA)

        assert result is False
        assert mock_step.await_count == 2

    @pytest.mark.asyncio
    async def test_continues_after_a_failed_image_pull(self):
        with (
            patch("demetra.services.daemons.deployer.run_deploy_step", new_callable=AsyncMock) as mock_step,
            patch("demetra.services.daemons.deployer.checkout_matches_sha", new_callable=AsyncMock) as mock_match,
            patch("demetra.services.daemons.deployer.wait_for_queue_drain", new_callable=AsyncMock) as mock_drain,
        ):
            mock_step.side_effect = [True, True, False, True, True, True]
            mock_match.return_value = True
            mock_drain.return_value = True
            result = await run_deploy(checkout_path=Path("/srv/checkout"), sha=SHA)

        assert result is True
        assert mock_step.await_count == 6

    @pytest.mark.asyncio
    async def test_continues_after_a_failed_nginx_reload(self):
        with (
            patch("demetra.services.daemons.deployer.run_deploy_step", new_callable=AsyncMock) as mock_step,
            patch("demetra.services.daemons.deployer.checkout_matches_sha", new_callable=AsyncMock) as mock_match,
            patch("demetra.services.daemons.deployer.wait_for_queue_drain", new_callable=AsyncMock) as mock_drain,
        ):
            mock_step.side_effect = [True, True, True, True, True, False]
            mock_match.return_value = True
            mock_drain.return_value = True
            result = await run_deploy(checkout_path=Path("/srv/checkout"), sha=SHA)

        assert result is True
        assert mock_step.await_count == 6

    @pytest.mark.asyncio
    async def test_aborts_before_building_when_the_pull_checked_out_another_commit(self):
        with (
            patch("demetra.services.daemons.deployer.run_deploy_step", new_callable=AsyncMock) as mock_step,
            patch("demetra.services.daemons.deployer.checkout_matches_sha", new_callable=AsyncMock) as mock_match,
            patch("demetra.services.daemons.deployer.wait_for_queue_drain", new_callable=AsyncMock) as mock_drain,
        ):
            mock_step.return_value = True
            mock_match.return_value = False
            mock_drain.return_value = True
            result = await run_deploy(checkout_path=Path("/srv/checkout"), sha=SHA)

        assert result is False
        assert mock_step.await_count == 1

    @pytest.mark.asyncio
    async def test_defers_the_recreate_when_a_job_started_during_the_build(self):
        with (
            patch("demetra.services.daemons.deployer.run_deploy_step", new_callable=AsyncMock) as mock_step,
            patch("demetra.services.daemons.deployer.checkout_matches_sha", new_callable=AsyncMock) as mock_match,
            patch("demetra.services.daemons.deployer.wait_for_queue_drain", new_callable=AsyncMock) as mock_drain,
        ):
            mock_step.return_value = True
            mock_match.return_value = True
            mock_drain.return_value = False
            result = await run_deploy(checkout_path=Path("/srv/checkout"), sha=SHA)

        assert result is False
        assert mock_step.await_count == 4
        assert [call.kwargs["name"] for call in mock_step.await_args_list] == [
            "pull",
            "build",
            "pull_images",
            "migrate",
        ]


class TestCheckoutMatchesSha:
    @pytest.mark.asyncio
    async def test_true_when_the_checkout_holds_the_gated_commit(self):
        with (
            patch("demetra.services.daemons.deployer.get_checkout_head_sha", new_callable=AsyncMock) as mock_head,
            patch(
                "demetra.services.daemons.deployer.checkout_has_no_local_changes", new_callable=AsyncMock
            ) as mock_clean,
        ):
            mock_head.return_value = SHA
            mock_clean.return_value = True
            assert await checkout_matches_sha(checkout_path=Path("/srv/checkout"), sha=SHA) is True

    @pytest.mark.asyncio
    async def test_false_when_master_advanced_after_the_gate(self):
        with (
            patch("demetra.services.daemons.deployer.get_checkout_head_sha", new_callable=AsyncMock) as mock_head,
            patch(
                "demetra.services.daemons.deployer.checkout_has_no_local_changes", new_callable=AsyncMock
            ) as mock_clean,
        ):
            mock_head.return_value = OTHER_SHA
            mock_clean.return_value = True
            assert await checkout_matches_sha(checkout_path=Path("/srv/checkout"), sha=SHA) is False

    @pytest.mark.asyncio
    async def test_false_when_the_head_cannot_be_read(self):
        with (
            patch("demetra.services.daemons.deployer.get_checkout_head_sha", new_callable=AsyncMock) as mock_head,
            patch(
                "demetra.services.daemons.deployer.checkout_has_no_local_changes", new_callable=AsyncMock
            ) as mock_clean,
        ):
            mock_head.return_value = None
            mock_clean.return_value = True
            assert await checkout_matches_sha(checkout_path=Path("/srv/checkout"), sha=SHA) is False

    @pytest.mark.asyncio
    async def test_false_when_the_working_tree_carries_an_unchecked_change(self):
        with (
            patch("demetra.services.daemons.deployer.get_checkout_head_sha", new_callable=AsyncMock) as mock_head,
            patch(
                "demetra.services.daemons.deployer.checkout_has_no_local_changes", new_callable=AsyncMock
            ) as mock_clean,
        ):
            mock_head.return_value = SHA
            mock_clean.return_value = False
            assert await checkout_matches_sha(checkout_path=Path("/srv/checkout"), sha=SHA) is False


class TestRunDeployStep:
    @pytest.mark.asyncio
    async def test_true_on_a_zero_exit(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "ok", "")
            assert await run_deploy_step(name="build", command=["docker"], checkout_path=Path("/srv")) is True

    @pytest.mark.asyncio
    async def test_false_on_a_non_zero_exit(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "boom")
            assert await run_deploy_step(name="build", command=["docker"], checkout_path=Path("/srv")) is False

    @pytest.mark.asyncio
    async def test_false_when_the_process_cannot_start(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = OSError("No such file or directory")
            assert await run_deploy_step(name="nginx_reload", command=["missing"], checkout_path=Path("/srv")) is False


class TestRecreateDeployer:
    def test_starts_a_detached_helper_so_the_self_kill_cannot_abort_it(self):
        command = recreate_deployer_command(checkout_path=Path("/srv/checkout"))

        assert command[1:4] == ["run", "--detach", "--rm"]
        assert "--entrypoint" in command
        assert command[command.index("--entrypoint") + 1] == "docker"

    def test_helper_mounts_the_socket_and_the_checkout(self):
        command = recreate_deployer_command(checkout_path=Path("/srv/checkout"))

        assert f"{DOCKER_SOCKET}:{DOCKER_SOCKET}" in command
        assert f"{Path('/srv/checkout')}:{Path('/srv/checkout')}" in command

    def test_helper_recreates_only_the_deployer_service(self):
        command = recreate_deployer_command(checkout_path=Path("/srv/checkout"))

        assert command[-1] == "deployer"
        assert "--force-recreate" in command
        assert command[command.index("--project-directory") + 1] == str(Path("/srv/checkout"))
        assert command[command.index("--file") + 1] == str(Path("/srv/checkout/docker-compose.yaml"))

    def test_helper_uses_the_built_image(self):
        command = recreate_deployer_command(checkout_path=Path("/srv/checkout"))

        assert DEPLOY_IMAGE in command

    @pytest.mark.asyncio
    async def test_returns_true_when_the_helper_is_started(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "helper-id", "")
            assert await recreate_deployer(checkout_path=Path("/srv/checkout")) is True

    @pytest.mark.asyncio
    async def test_logs_and_returns_false_when_the_helper_fails(self):
        with patch("demetra.services.daemons.deployer.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "Cannot connect to the Docker daemon")
            assert await recreate_deployer(checkout_path=Path("/srv/checkout")) is False


class TestMakefileParity:
    def _recipe(self, target: str) -> list[str]:
        makefile = (Path(__file__).resolve().parents[1] / "Makefile").read_text().splitlines()
        recipe, in_target = [], False
        for line in makefile:
            if line.startswith(f"{target}:"):
                in_target = True
                continue
            if in_target and line.startswith("\t"):
                recipe.append(line.strip())
            elif in_target and line.strip():
                break
        return recipe

    def test_deploy_recipe_runs_under_the_shared_deploy_lock(self):
        recipe = self._recipe("deploy")

        assert len(recipe) == 1
        assert recipe[0].endswith("deploy-steps")
        assert "demetra.deploy_lock" in recipe[0]

    def test_recreate_step_matches_the_makefile_deploy_steps_target(self):
        recipe = self._recipe("deploy-steps")
        makefile_up = next(command for command in recipe if "--force-recreate" in command).split()
        daemon_up = dict(build_deploy_steps(checkout_path=Path("/srv/checkout")))["up"]

        assert makefile_up[-6:-1] == list(DEPLOY["compose_services"])
        assert makefile_up[-1] == "deployer"
        assert daemon_up[-5:] == list(DEPLOY["compose_services"])
        assert makefile_up[makefile_up.index("--scale") + 1] == daemon_up[daemon_up.index("--scale") + 1]

    def test_migrate_step_matches_the_makefile_deploy_steps_target(self):
        recipe = self._recipe("deploy-steps")
        makefile_migrate = next(command for command in recipe if "--abort-on-container-failure" in command).split()
        daemon_migrate = dict(build_deploy_steps(checkout_path=Path("/srv/checkout")))["migrate"]

        assert makefile_migrate[-3:] == daemon_migrate[-3:]


class TestRunDeployCycle:
    @pytest.fixture
    def cycle_mocks(self, tmp_path: Path):
        lock = MagicMock()
        lock.acquire.return_value = True
        with (
            patch("demetra.services.daemons.deployer.default_state_path", return_value=tmp_path / "state.json"),
            patch("demetra.services.daemons.deployer.get_remote_master_sha", new_callable=AsyncMock) as mock_remote,
            patch("demetra.services.daemons.deployer.get_running_revision", new_callable=AsyncMock) as mock_revision,
            patch("demetra.services.daemons.deployer.get_origin_repository", new_callable=AsyncMock) as mock_repo,
            patch("demetra.services.daemons.deployer.get_ci_status", new_callable=AsyncMock) as mock_ci,
            patch("demetra.services.daemons.deployer.wait_for_queue_drain", new_callable=AsyncMock) as mock_drain,
            patch("demetra.services.daemons.deployer.run_deploy", new_callable=AsyncMock) as mock_deploy,
            patch("demetra.services.daemons.deployer.recreate_deployer", new_callable=AsyncMock) as mock_recreate,
            patch("demetra.services.daemons.deployer.connection") as mock_connection,
        ):
            mock_remote.return_value = SHA
            mock_revision.return_value = None
            mock_repo.return_value = "manti-by/demetra"
            mock_ci.return_value = CI_STATUS_PASSED
            mock_drain.return_value = True
            mock_deploy.return_value = True
            mock_recreate.return_value = True
            mock_connection.lock.return_value = lock
            yield {
                "remote": mock_remote,
                "revision": mock_revision,
                "ci": mock_ci,
                "drain": mock_drain,
                "deploy": mock_deploy,
                "recreate": mock_recreate,
                "lock": lock,
                "connection": mock_connection,
                "state_path": tmp_path / "state.json",
            }

    @pytest.mark.asyncio
    async def test_deploys_a_new_commit_once(self, cycle_mocks):
        await run_deploy_cycle()

        assert cycle_mocks["deploy"].await_count == 1
        cycle_mocks["deploy"].assert_awaited_once_with(checkout_path=DEPLOY["host_checkout"], sha=SHA)
        assert load_state(path=cycle_mocks["state_path"]).last_deployed_sha == SHA

    @pytest.mark.asyncio
    async def test_holds_a_lock_covering_the_whole_deploy(self, cycle_mocks):
        await run_deploy_cycle()

        lock_timeout = cycle_mocks["connection"].lock.call_args.kwargs["timeout"]
        assert lock_timeout == deploy_lock_timeout(checkout_path=DEPLOY["host_checkout"])
        assert lock_timeout > DEPLOY["step_timeout"]

    @pytest.mark.asyncio
    async def test_recreates_the_deployer_after_a_successful_deploy(self, cycle_mocks):
        def _check_state(*, checkout_path):
            assert load_state(path=cycle_mocks["state_path"]).last_deployed_sha == SHA
            return True

        cycle_mocks["recreate"].side_effect = _check_state

        await run_deploy_cycle()

        cycle_mocks["recreate"].assert_awaited_once_with(checkout_path=DEPLOY["host_checkout"])

    @pytest.mark.asyncio
    async def test_does_not_recreate_the_deployer_after_a_failed_deploy(self, cycle_mocks):
        cycle_mocks["deploy"].return_value = False

        await run_deploy_cycle()

        cycle_mocks["recreate"].assert_not_awaited()

    @pytest.mark.asyncio
    async def test_does_not_redeploy_the_same_commit(self, cycle_mocks):
        save_state(path=cycle_mocks["state_path"], state=DeployState(last_deployed_sha=SHA))

        await run_deploy_cycle()

        assert cycle_mocks["deploy"].await_count == 0

    @pytest.mark.asyncio
    async def test_seeds_the_state_from_the_running_image_revision(self, cycle_mocks):
        cycle_mocks["revision"].return_value = OTHER_SHA

        await run_deploy_cycle()

        assert load_state(path=cycle_mocks["state_path"]).last_deployed_sha == SHA

    @pytest.mark.asyncio
    async def test_leaves_the_commit_eligible_without_a_deployed_revision(self, cycle_mocks):
        cycle_mocks["revision"].return_value = None

        await run_deploy_cycle()

        cycle_mocks["deploy"].assert_awaited_once_with(checkout_path=DEPLOY["host_checkout"], sha=SHA)
        assert load_state(path=cycle_mocks["state_path"]).last_deployed_sha == SHA

    @pytest.mark.asyncio
    async def test_does_not_seed_from_a_deployed_revision_that_is_already_current(self, cycle_mocks):
        cycle_mocks["revision"].return_value = SHA

        await run_deploy_cycle()

        assert cycle_mocks["deploy"].await_count == 0

    @pytest.mark.asyncio
    async def test_skips_the_deploy_while_ci_is_pending(self, cycle_mocks):
        cycle_mocks["ci"].return_value = CI_STATUS_PENDING

        await run_deploy_cycle()

        assert cycle_mocks["deploy"].await_count == 0

    @pytest.mark.asyncio
    async def test_skips_the_deploy_when_ci_failed_and_records_the_failure(self, cycle_mocks):
        cycle_mocks["ci"].return_value = CI_STATUS_FAILED

        await run_deploy_cycle()

        assert cycle_mocks["deploy"].await_count == 0
        assert load_state(path=cycle_mocks["state_path"]).last_failed_sha == SHA

    @pytest.mark.asyncio
    async def test_skips_the_deploy_when_the_check_runs_cannot_be_read(self, cycle_mocks):
        cycle_mocks["ci"].return_value = CI_STATUS_UNKNOWN

        await run_deploy_cycle()

        assert cycle_mocks["deploy"].await_count == 0
        state = load_state(path=cycle_mocks["state_path"])
        assert state.last_failed_sha is None
        assert state.last_error is None

    @pytest.mark.asyncio
    async def test_a_read_failure_does_not_block_the_next_cycle(self, cycle_mocks):
        cycle_mocks["ci"].side_effect = [CI_STATUS_UNKNOWN, CI_STATUS_PASSED]

        await run_deploy_cycle()
        await run_deploy_cycle()

        assert cycle_mocks["deploy"].await_count == 1
        assert load_state(path=cycle_mocks["state_path"]).last_deployed_sha == SHA

    @pytest.mark.asyncio
    async def test_clears_a_stale_ci_failure_when_the_gate_turns_green(self, cycle_mocks):
        save_state(
            path=cycle_mocks["state_path"],
            state=DeployState(last_deployed_sha=OTHER_SHA, last_failed_sha=SHA, last_error="CI checks failed"),
        )

        await run_deploy_cycle()

        assert cycle_mocks["deploy"].await_count == 1
        state = load_state(path=cycle_mocks["state_path"])
        assert state.last_deployed_sha == SHA
        assert state.last_failed_sha is None
        assert state.last_error is None

    @pytest.mark.asyncio
    async def test_skips_the_deploy_while_a_job_is_running(self, cycle_mocks):
        cycle_mocks["drain"].return_value = False

        await run_deploy_cycle()

        assert cycle_mocks["deploy"].await_count == 0

    @pytest.mark.asyncio
    async def test_defers_the_deploy_when_master_moved_during_the_drain(self, cycle_mocks):
        cycle_mocks["remote"].side_effect = [SHA, OTHER_SHA]

        await run_deploy_cycle()

        assert cycle_mocks["deploy"].await_count == 0

    @pytest.mark.asyncio
    async def test_skips_the_deploy_when_another_deploy_holds_the_lock(self, cycle_mocks):
        cycle_mocks["lock"].acquire.return_value = False

        await run_deploy_cycle()

        assert cycle_mocks["deploy"].await_count == 0

    @pytest.mark.asyncio
    async def test_failed_deploy_is_retried_on_the_next_cycle(self, cycle_mocks):
        cycle_mocks["deploy"].return_value = False

        await run_deploy_cycle()

        state = load_state(path=cycle_mocks["state_path"])
        assert state.last_deployed_sha is None
        assert state.last_failed_sha == SHA
        assert state.last_error == "deploy failed"

    @pytest.mark.asyncio
    async def test_rechecks_the_state_after_acquiring_the_lock(self, cycle_mocks):
        def _concurrent_deploy(*, timeout):
            save_state(
                path=cycle_mocks["state_path"], state=DeployState(last_deployed_sha=SHA, last_deploy_at=time.time())
            )
            return True

        cycle_mocks["drain"].side_effect = _concurrent_deploy

        await run_deploy_cycle()

        assert cycle_mocks["deploy"].await_count == 0

    @pytest.mark.asyncio
    async def test_records_a_pending_recreate_before_releasing_the_lock(self, cycle_mocks):
        seen: list[bool] = []

        def _check_lock(*, checkout_path):
            seen.append(cycle_mocks["lock"].release.called)
            return True

        cycle_mocks["recreate"].side_effect = _check_lock

        await run_deploy_cycle()

        assert seen == [True]
        assert load_state(path=cycle_mocks["state_path"]).pending_recreate is False

    @pytest.mark.asyncio
    async def test_clears_the_pending_recreate_before_dispatching_the_helper(self, cycle_mocks):
        seen: list[bool] = []

        def _check_state(*, checkout_path):
            seen.append(load_state(path=cycle_mocks["state_path"]).pending_recreate)
            return True

        cycle_mocks["recreate"].side_effect = _check_state

        await run_deploy_cycle()

        assert seen == [False]

    @pytest.mark.asyncio
    async def test_keeps_the_recreate_pending_when_the_helper_fails(self, cycle_mocks):
        cycle_mocks["recreate"].return_value = False

        await run_deploy_cycle()

        state = load_state(path=cycle_mocks["state_path"])
        assert state.pending_recreate is True
        assert state.last_deployed_sha == SHA

    @pytest.mark.asyncio
    async def test_retries_a_pending_recreate_without_a_new_deploy(self, cycle_mocks):
        save_state(
            path=cycle_mocks["state_path"],
            state=DeployState(last_deployed_sha=SHA, pending_recreate=True),
        )

        await run_deploy_cycle()

        cycle_mocks["recreate"].assert_awaited_once_with(checkout_path=DEPLOY["host_checkout"])
        assert cycle_mocks["deploy"].await_count == 0
        assert load_state(path=cycle_mocks["state_path"]).pending_recreate is False
