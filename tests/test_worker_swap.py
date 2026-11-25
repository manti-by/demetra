from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.library.exceptions import DeployStateError
from demetra.library.models import DeployState
from demetra.services.daemons.worker_swap import (
    LEGACY_WORKER_SERVICE,
    SWAP_STEP_BUDGET,
    WORKER_REPLICAS,
    WORKER_SLOTS,
    bootstrap_workers,
    disable_restart_command,
    escalate_draining_workers,
    list_container_ids,
    list_containers_command,
    maintain_workers,
    other_slot,
    reap_service,
    remove_command,
    retire_staging_workers,
    run_swap_command,
    signal_command,
    start_service_command,
    swap_workers,
    worker_service,
)
from demetra.settings import DEPLOY, SUBPROCESS_TIMEOUT


CHECKOUT = Path("/srv/checkout")
STATE_PATH = CHECKOUT / "state.json"


class TestSlotHelpers:
    def test_other_slot_toggles_between_the_two_generations(self):
        assert other_slot(slot="blue") == "green"
        assert other_slot(slot="green") == "blue"

    def test_worker_service_names_each_generation(self):
        assert [worker_service(slot=slot) for slot in WORKER_SLOTS] == ["worker-blue", "worker-green"]


class TestStepBudget:
    def test_covers_every_command_of_the_longest_swap_path(self):
        retirement = 2 * WORKER_REPLICAS + 2
        reaping = 4
        staging_start = 1
        container_lists = 2
        restart_disable = 1
        signals = WORKER_REPLICAS
        checkout_reads = 2

        worst_case = retirement + reaping + staging_start + container_lists + restart_disable + signals + checkout_reads

        maintenance = 3 * reaping + 2 * WORKER_REPLICAS
        assert SWAP_STEP_BUDGET >= worst_case
        assert SWAP_STEP_BUDGET >= maintenance


class TestSwapCommands:
    def test_lists_running_containers_with_the_checkout_env_file(self):
        command = list_containers_command(checkout_path=CHECKOUT, service="worker-blue")

        assert command[-1] == "worker-blue"
        assert "ps" in command
        assert "--quiet" in command
        assert "--filter" not in command
        assert command[command.index("--env-file") + 1] == str(CHECKOUT / ".env.docker")

    def test_lists_exited_containers_with_a_status_filter(self):
        command = list_containers_command(checkout_path=CHECKOUT, service="worker-green", exited=True)

        assert "--all" in command
        assert command[command.index("--filter") + 1] == "status=exited"

    def test_finds_legacy_worker_containers_by_compose_label(self):
        command = list_containers_command(checkout_path=CHECKOUT, service=LEGACY_WORKER_SERVICE, exited=True)

        assert command[:2] == [str(DEPLOY["docker_path"]), "ps"]
        assert "label=com.docker.compose.project=demetra" in command
        assert "label=com.docker.compose.service=worker" in command
        assert "status=exited" in command

    def test_signal_sends_one_term_to_every_listed_container(self):
        assert signal_command(container_ids=["c1", "c2"]) == [
            str(DEPLOY["docker_path"]),
            "kill",
            "--signal",
            "TERM",
            "c1",
            "c2",
        ]

    def test_disable_restart_prevents_docker_from_reviving_a_draining_worker(self):
        assert disable_restart_command(container_ids=["c1", "c2"]) == [
            str(DEPLOY["docker_path"]),
            "update",
            "--restart",
            "no",
            "c1",
            "c2",
        ]

    def test_remove_only_takes_container_ids_unless_forced(self):
        assert remove_command(container_ids=["c1"]) == [str(DEPLOY["docker_path"]), "rm", "c1"]
        assert remove_command(container_ids=["c1"], force=True) == [
            str(DEPLOY["docker_path"]),
            "rm",
            "--force",
            "c1",
        ]

    def test_start_service_scales_one_slot_without_dependencies(self):
        command = start_service_command(checkout_path=CHECKOUT, service="worker-green", replicas=WORKER_REPLICAS)

        assert "--detach" in command
        assert "--no-deps" in command
        assert "--force-recreate" not in command
        assert command[-3:] == ["--scale", f"worker-green={WORKER_REPLICAS}", "worker-green"]


class TestRunSwapCommand:
    @pytest.mark.asyncio
    async def test_returns_the_captured_stdout_on_success(self):
        with patch(
            "demetra.services.daemons.worker_swap.run_command", new_callable=AsyncMock, return_value=(0, "c1\n", "")
        ):
            succeeded, output = await run_swap_command(checkout_path=CHECKOUT, command=["docker", "ps"])

        assert succeeded is True
        assert output == "c1"

    @pytest.mark.asyncio
    async def test_returns_false_on_a_non_zero_exit(self):
        with patch(
            "demetra.services.daemons.worker_swap.run_command", new_callable=AsyncMock, return_value=(1, "", "boom")
        ):
            succeeded, output = await run_swap_command(checkout_path=CHECKOUT, command=["docker", "kill"])

        assert succeeded is False
        assert output == ""

    @pytest.mark.asyncio
    async def test_returns_false_when_the_process_cannot_start(self):
        with patch(
            "demetra.services.daemons.worker_swap.run_command", new_callable=AsyncMock, side_effect=OSError("missing")
        ):
            succeeded, _ = await run_swap_command(checkout_path=CHECKOUT, command=["missing"])

        assert succeeded is False


class TestListContainerIds:
    @pytest.mark.asyncio
    async def test_splits_the_queried_ids(self):
        with patch(
            "demetra.services.daemons.worker_swap.run_swap_command",
            new_callable=AsyncMock,
            return_value=(True, "c1 c2"),
        ):
            assert await list_container_ids(checkout_path=CHECKOUT, service="worker-blue") == ["c1", "c2"]

    @pytest.mark.asyncio
    async def test_returns_none_when_the_query_fails(self):
        with patch(
            "demetra.services.daemons.worker_swap.run_swap_command", new_callable=AsyncMock, return_value=(False, "")
        ):
            assert await list_container_ids(checkout_path=CHECKOUT, service="worker-blue") is None


class TestReapService:
    @pytest.mark.asyncio
    async def test_removes_exited_containers_and_prunes_their_drain_state(self):
        state = DeployState(draining_workers={"c1": 1.0, "c2": 2.0})

        async def _ids(*, checkout_path, service, exited=False):
            return ["c1"] if exited else ["c2"]

        with (
            patch("demetra.services.daemons.worker_swap.list_container_ids", new_callable=AsyncMock) as mock_ids,
            patch("demetra.services.daemons.worker_swap.run_swap_command", new_callable=AsyncMock) as mock_run,
        ):
            mock_ids.side_effect = _ids
            mock_run.return_value = (True, "")

            assert (
                await reap_service(
                    checkout_path=CHECKOUT, service="worker-blue", state=state, live_service="worker-green"
                )
                is True
            )

        commands = [call.kwargs["command"] for call in mock_run.await_args_list]
        assert remove_command(container_ids=["c1"]) in commands
        assert all("kill" not in command for command in commands)
        assert state.draining_workers == {"c2": 2.0}

    @pytest.mark.asyncio
    async def test_scales_an_empty_non_live_slot_down_to_zero(self):
        state = DeployState()

        with (
            patch("demetra.services.daemons.worker_swap.list_container_ids", new_callable=AsyncMock, return_value=[]),
            patch(
                "demetra.services.daemons.worker_swap.run_swap_command", new_callable=AsyncMock, return_value=(True, "")
            ) as mock_run,
        ):
            assert (
                await reap_service(
                    checkout_path=CHECKOUT, service="worker-blue", state=state, live_service="worker-green"
                )
                is True
            )

        mock_run.assert_awaited_once()
        assert mock_run.await_args_list[0].kwargs["command"] == start_service_command(
            checkout_path=CHECKOUT, service="worker-blue", replicas=0
        )

    @pytest.mark.asyncio
    async def test_never_scales_the_live_slot_or_a_slot_being_started(self):
        state = DeployState()

        with (
            patch("demetra.services.daemons.worker_swap.list_container_ids", new_callable=AsyncMock, return_value=[]),
            patch(
                "demetra.services.daemons.worker_swap.run_swap_command", new_callable=AsyncMock, return_value=(True, "")
            ) as mock_run,
        ):
            await reap_service(
                checkout_path=CHECKOUT, service="worker-blue", state=state, live_service="worker-blue", scale_down=False
            )

        mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_false_when_removing_a_container_fails(self):
        state = DeployState()

        async def _ids(*, checkout_path, service, exited=False):
            return ["c1"] if exited else []

        with (
            patch("demetra.services.daemons.worker_swap.list_container_ids", new_callable=AsyncMock) as mock_ids,
            patch(
                "demetra.services.daemons.worker_swap.run_swap_command",
                new_callable=AsyncMock,
                return_value=(False, ""),
            ),
        ):
            mock_ids.side_effect = _ids

            assert (
                await reap_service(
                    checkout_path=CHECKOUT, service="worker-blue", state=state, live_service="worker-green"
                )
                is False
            )

        assert state.draining_workers == {}

    @pytest.mark.asyncio
    async def test_aborts_when_a_container_query_fails(self):
        with patch(
            "demetra.services.daemons.worker_swap.list_container_ids", new_callable=AsyncMock, return_value=None
        ):
            assert (
                await reap_service(
                    checkout_path=CHECKOUT,
                    service="worker-blue",
                    state=DeployState(),
                    live_service="worker-green",
                )
                is False
            )


class TestRetireStagingWorkers:
    @pytest.mark.asyncio
    async def test_preserves_a_draining_container_in_the_staging_slot(self):
        state = DeployState(draining_workers={"c1": 10.0})

        with (
            patch(
                "demetra.services.daemons.worker_swap.list_container_ids",
                new_callable=AsyncMock,
                return_value=["c1"],
            ),
            patch(
                "demetra.services.daemons.worker_swap.run_swap_command", new_callable=AsyncMock, return_value=(True, "")
            ) as mock_run,
        ):
            assert await retire_staging_workers(checkout_path=CHECKOUT, service="worker-green", state=state) is False

        mock_run.assert_not_awaited()
        assert state.draining_workers == {"c1": 10.0}

    @pytest.mark.asyncio
    async def test_force_stops_and_removes_a_staging_container_that_is_not_draining(self):
        state = DeployState()

        with (
            patch(
                "demetra.services.daemons.worker_swap.list_container_ids",
                new_callable=AsyncMock,
                return_value=["c1"],
            ),
            patch(
                "demetra.services.daemons.worker_swap.run_swap_command", new_callable=AsyncMock, return_value=(True, "")
            ) as mock_run,
            patch("demetra.services.daemons.worker_swap.time.time", return_value=1000.0),
        ):
            assert await retire_staging_workers(checkout_path=CHECKOUT, service="worker-green", state=state) is True

        commands = [call.kwargs["command"] for call in mock_run.await_args_list]
        assert disable_restart_command(container_ids=["c1"]) in commands
        assert signal_command(container_ids=["c1"]) in commands
        assert remove_command(container_ids=["c1"], force=True) in commands
        assert state.draining_workers == {}

    @pytest.mark.asyncio
    async def test_does_nothing_when_the_slot_is_empty(self):
        with (
            patch("demetra.services.daemons.worker_swap.list_container_ids", new_callable=AsyncMock, return_value=[]),
            patch("demetra.services.daemons.worker_swap.run_swap_command", new_callable=AsyncMock) as mock_run,
        ):
            assert (
                await retire_staging_workers(checkout_path=CHECKOUT, service="worker-green", state=DeployState())
                is True
            )

        mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_aborts_when_the_slot_cannot_be_listed(self):
        with patch(
            "demetra.services.daemons.worker_swap.list_container_ids", new_callable=AsyncMock, return_value=None
        ):
            assert (
                await retire_staging_workers(checkout_path=CHECKOUT, service="worker-green", state=DeployState())
                is False
            )


class TestSwapWorkers:
    @pytest.fixture
    def swap_mocks(self):
        with (
            patch("demetra.services.daemons.worker_swap.retire_staging_workers", new_callable=AsyncMock) as mock_retire,
            patch("demetra.services.daemons.worker_swap.reap_service", new_callable=AsyncMock) as mock_reap,
            patch("demetra.services.daemons.worker_swap.run_swap_command", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.daemons.worker_swap.list_container_ids", new_callable=AsyncMock) as mock_ids,
            patch("demetra.services.daemons.worker_swap.save_state") as mock_save,
            patch("demetra.services.daemons.worker_swap.time.time", return_value=1000.0),
        ):
            mock_retire.return_value = True
            mock_reap.return_value = True
            mock_run.return_value = (True, "")
            mock_ids.return_value = []
            yield {
                "retire": mock_retire,
                "reap": mock_reap,
                "run": mock_run,
                "ids": mock_ids,
                "save": mock_save,
            }

    def _set_running(self, mocks: dict, containers: dict[str, list[str]]) -> None:
        async def _ids(*, checkout_path, service, exited=False):
            return containers.get(service, [])

        mocks["ids"].side_effect = _ids

    @pytest.mark.asyncio
    async def test_starts_staging_before_signalling_the_live_generation(self, swap_mocks):
        state = DeployState(worker_slot="blue")
        self._set_running(mocks=swap_mocks, containers={"worker-blue": ["c1"]})

        assert await swap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=state) is True

        commands = [call.kwargs["command"] for call in swap_mocks["run"].await_args_list]
        assert "worker-green=4" in commands[0]
        assert commands[1] == disable_restart_command(container_ids=["c1"])
        assert commands[2] == signal_command(container_ids=["c1"])
        swap_mocks["retire"].assert_awaited_once_with(checkout_path=CHECKOUT, service="worker-green", state=state)
        swap_mocks["reap"].assert_awaited_once_with(
            checkout_path=CHECKOUT, service="worker-green", state=state, live_service="worker-blue", scale_down=False
        )
        assert state.worker_slot == "green"
        assert state.draining_workers == {"c1": 1000.0}
        swap_mocks["save"].assert_any_call(path=STATE_PATH, state=state)

    @pytest.mark.asyncio
    async def test_does_not_signal_a_container_that_is_already_draining(self, swap_mocks):
        state = DeployState(worker_slot="blue", draining_workers={"c1": 10.0})
        self._set_running(mocks=swap_mocks, containers={"worker-blue": ["c1", "c2"]})

        await swap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=state)

        commands = [call.kwargs["command"] for call in swap_mocks["run"].await_args_list]
        assert commands[1] == disable_restart_command(container_ids=["c2"])
        assert commands[2] == signal_command(container_ids=["c2"])
        assert state.draining_workers == {"c1": 10.0, "c2": 1000.0}

    @pytest.mark.asyncio
    async def test_signals_the_legacy_worker_on_the_first_swap(self, swap_mocks):
        state = DeployState(worker_slot="blue")
        self._set_running(mocks=swap_mocks, containers={LEGACY_WORKER_SERVICE: ["legacy-1"]})

        await swap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=state)

        commands = [call.kwargs["command"] for call in swap_mocks["run"].await_args_list]
        assert commands[2] == signal_command(container_ids=["legacy-1"])

    @pytest.mark.asyncio
    async def test_aborts_when_staging_cannot_start(self, swap_mocks):
        state = DeployState(worker_slot="blue")
        swap_mocks["run"].return_value = (False, "")

        assert await swap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=state) is False

        assert state.worker_slot == "blue"
        assert state.draining_workers == {}
        swap_mocks["save"].assert_not_called()

    @pytest.mark.asyncio
    async def test_aborts_when_the_live_signal_fails(self, swap_mocks):
        state = DeployState(worker_slot="blue")
        self._set_running(mocks=swap_mocks, containers={"worker-blue": ["c1"]})
        swap_mocks["run"].side_effect = [(True, ""), (True, ""), (False, "")]

        assert await swap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=state) is False

        assert state.worker_slot == "blue"
        assert state.draining_workers == {}
        swap_mocks["save"].assert_not_called()

    @pytest.mark.asyncio
    async def test_aborts_when_the_restart_policy_cannot_be_disabled(self, swap_mocks):
        state = DeployState(worker_slot="blue")
        self._set_running(mocks=swap_mocks, containers={"worker-blue": ["c1"]})
        swap_mocks["run"].side_effect = [(True, ""), (False, "")]

        assert await swap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=state) is False

        assert state.worker_slot == "blue"
        assert swap_mocks["run"].await_count == 2

    @pytest.mark.asyncio
    async def test_persists_each_signal_before_a_partial_batch_failure(self, swap_mocks):
        state = DeployState(worker_slot="blue")
        self._set_running(mocks=swap_mocks, containers={"worker-blue": ["c1", "c2"]})
        swap_mocks["run"].side_effect = [(True, ""), (True, ""), (True, ""), (False, "")]

        assert await swap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=state) is False

        assert state.draining_workers == {"c1": 1000.0}
        swap_mocks["save"].assert_called_once_with(path=STATE_PATH, state=state)
        assert [call.kwargs["command"] for call in swap_mocks["run"].await_args_list] == [
            start_service_command(checkout_path=CHECKOUT, service="worker-green", replicas=WORKER_REPLICAS),
            disable_restart_command(container_ids=["c1", "c2"]),
            signal_command(container_ids=["c1"]),
            signal_command(container_ids=["c2"]),
        ]

    @pytest.mark.asyncio
    async def test_retry_does_not_re_signal_an_id_recorded_by_the_failed_batch(self, swap_mocks):
        state = DeployState(worker_slot="blue", draining_workers={"c1": 10.0})
        self._set_running(mocks=swap_mocks, containers={"worker-blue": ["c1", "c2"]})
        swap_mocks["run"].side_effect = [(True, ""), (True, ""), (True, "")]

        assert await swap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=state) is True

        assert [call.kwargs["command"] for call in swap_mocks["run"].await_args_list] == [
            start_service_command(checkout_path=CHECKOUT, service="worker-green", replicas=WORKER_REPLICAS),
            disable_restart_command(container_ids=["c2"]),
            signal_command(container_ids=["c2"]),
        ]

    @pytest.mark.asyncio
    async def test_aborts_on_a_failed_signal_checkpoint_but_keeps_its_marker(self, swap_mocks):
        state = DeployState(worker_slot="blue")
        self._set_running(mocks=swap_mocks, containers={"worker-blue": ["c1"]})
        swap_mocks["save"].side_effect = DeployStateError("disk full")

        assert await swap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=state) is False

        assert state.worker_slot == "blue"
        assert state.draining_workers == {"c1": 1000.0}
        swap_mocks["save"].assert_called_once_with(path=STATE_PATH, state=state)

    @pytest.mark.asyncio
    async def test_aborts_when_the_final_slot_checkpoint_fails(self, swap_mocks):
        state = DeployState(worker_slot="blue")
        self._set_running(mocks=swap_mocks, containers={"worker-blue": ["c1"]})
        swap_mocks["save"].side_effect = [None, DeployStateError("disk full")]

        assert await swap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=state) is False

        assert swap_mocks["save"].call_count == 2
        assert state.worker_slot == "green"

    @pytest.mark.asyncio
    async def test_aborts_when_the_staging_slot_cannot_be_retired(self, swap_mocks):
        state = DeployState(worker_slot="blue")
        swap_mocks["retire"].return_value = False

        assert await swap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=state) is False

        swap_mocks["run"].assert_not_awaited()
        assert state.worker_slot == "blue"
        swap_mocks["save"].assert_not_called()

    @pytest.mark.asyncio
    async def test_aborts_when_the_live_slot_cannot_be_listed(self, swap_mocks):
        state = DeployState(worker_slot="blue")
        swap_mocks["ids"].return_value = None

        assert await swap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=state) is False

        assert state.worker_slot == "blue"
        swap_mocks["save"].assert_not_called()

    @pytest.mark.asyncio
    async def test_aborts_when_the_legacy_workers_cannot_be_listed(self, swap_mocks):
        state = DeployState(worker_slot="blue")

        async def _ids(*, checkout_path, service, exited=False):
            return None if service == LEGACY_WORKER_SERVICE else []

        swap_mocks["ids"].side_effect = _ids

        assert await swap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=state) is False

        assert state.worker_slot == "blue"
        swap_mocks["save"].assert_not_called()


class TestBootstrapWorkers:
    @pytest.mark.asyncio
    async def test_scales_the_recorded_live_generation_to_four(self):
        state = DeployState(worker_slot="green")

        with (
            patch(
                "demetra.services.daemons.worker_swap.run_swap_command",
                new_callable=AsyncMock,
                return_value=(True, ""),
            ) as mock_run,
            patch("demetra.services.daemons.worker_swap.save_state") as mock_save,
        ):
            assert await bootstrap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=state) is True

        commands = [call.kwargs["command"] for call in mock_run.await_args_list]
        assert "worker-blue=0" in commands[0]
        assert "worker-green=4" in commands[1]
        mock_save.assert_called_once_with(path=STATE_PATH, state=state)

    @pytest.mark.asyncio
    async def test_a_fresh_state_boots_blue(self):
        with (
            patch(
                "demetra.services.daemons.worker_swap.run_swap_command",
                new_callable=AsyncMock,
                return_value=(True, ""),
            ) as mock_run,
            patch("demetra.services.daemons.worker_swap.save_state"),
        ):
            assert await bootstrap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=DeployState()) is True

        commands = [call.kwargs["command"] for call in mock_run.await_args_list]
        assert "worker-blue=4" in commands[0]
        assert "worker-green=0" in commands[1]

    @pytest.mark.asyncio
    async def test_aborts_when_a_slot_cannot_be_scaled(self):
        with (
            patch(
                "demetra.services.daemons.worker_swap.run_swap_command",
                new_callable=AsyncMock,
                return_value=(False, ""),
            ),
            patch("demetra.services.daemons.worker_swap.save_state") as mock_save,
        ):
            assert await bootstrap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=DeployState()) is False

        mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_reports_a_failed_state_checkpoint(self):
        with (
            patch(
                "demetra.services.daemons.worker_swap.run_swap_command",
                new_callable=AsyncMock,
                return_value=(True, ""),
            ),
            patch("demetra.services.daemons.worker_swap.save_state", side_effect=DeployStateError("disk full")),
        ):
            assert await bootstrap_workers(checkout_path=CHECKOUT, state_path=STATE_PATH, state=DeployState()) is False


class TestEscalateDrainingWorkers:
    @pytest.mark.asyncio
    async def test_force_stops_a_worker_past_the_job_timeout(self):
        state = DeployState(draining_workers={"c1": 0.0, "c2": SUBPROCESS_TIMEOUT})

        async def _run(*, checkout_path, command):
            return (True, "true") if command[1] == "inspect" else (True, "")

        with (
            patch(
                "demetra.services.daemons.worker_swap.run_swap_command", new_callable=AsyncMock, side_effect=_run
            ) as mock_run,
            patch("demetra.services.daemons.worker_swap.time.time", return_value=float(SUBPROCESS_TIMEOUT + 100)),
        ):
            assert await escalate_draining_workers(checkout_path=CHECKOUT, state=state) == ["c1"]

        commands = [call.kwargs["command"] for call in mock_run.await_args_list]
        assert signal_command(container_ids=["c1"]) in commands
        assert state.draining_workers["c1"] == float(SUBPROCESS_TIMEOUT + 100)
        assert state.draining_workers["c2"] == SUBPROCESS_TIMEOUT

    @pytest.mark.asyncio
    async def test_leaves_a_worker_within_the_timeout_alone(self):
        state = DeployState(draining_workers={"c1": 500.0})

        with (
            patch("demetra.services.daemons.worker_swap.run_swap_command", new_callable=AsyncMock) as mock_run,
            patch("demetra.services.daemons.worker_swap.time.time", return_value=600.0),
        ):
            assert await escalate_draining_workers(checkout_path=CHECKOUT, state=state) == []

        mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_a_container_that_already_exited(self):
        state = DeployState(draining_workers={"c1": 0.0})

        with (
            patch(
                "demetra.services.daemons.worker_swap.run_swap_command",
                new_callable=AsyncMock,
                return_value=(True, "false"),
            ) as mock_run,
            patch("demetra.services.daemons.worker_swap.time.time", return_value=float(SUBPROCESS_TIMEOUT + 100)),
        ):
            assert await escalate_draining_workers(checkout_path=CHECKOUT, state=state) == []

        assert len(mock_run.await_args_list) == 1


class TestMaintainWorkers:
    @pytest.mark.asyncio
    async def test_reaps_both_generations_and_the_legacy_service(self):
        state = DeployState(worker_slot="green")

        with (
            patch("demetra.services.daemons.worker_swap.load_state", return_value=state),
            patch("demetra.services.daemons.worker_swap.reap_service", new_callable=AsyncMock) as mock_reap,
            patch(
                "demetra.services.daemons.worker_swap.escalate_draining_workers", new_callable=AsyncMock
            ) as mock_escalate,
            patch(
                "demetra.services.daemons.worker_swap.requeue_abandoned_jobs", return_value=["job-1"]
            ) as mock_requeue,
            patch("demetra.services.daemons.worker_swap.save_state") as mock_save,
        ):
            mock_reap.return_value = True
            mock_escalate.return_value = []

            await maintain_workers(checkout_path=CHECKOUT, state_path=STATE_PATH)

        assert [call.kwargs["service"] for call in mock_reap.await_args_list] == [
            "worker-blue",
            "worker-green",
            LEGACY_WORKER_SERVICE,
        ]
        assert all(call.kwargs["live_service"] == "worker-green" for call in mock_reap.await_args_list)
        mock_escalate.assert_awaited_once_with(checkout_path=CHECKOUT, state=state)
        mock_requeue.assert_called_once_with()
        mock_save.assert_called_once_with(path=STATE_PATH, state=state)
