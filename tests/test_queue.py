from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from redis.exceptions import RedisError
from rq.exceptions import NoSuchJobError
from rq.job import JobStatus
from rq.registry import StartedJobRegistry

from demetra.services.persistence.queue import (
    REMOVE_EXPIRED_MEMBERS_SCRIPT,
    WORKFLOW_JOB_PATH,
    enqueue_workflow,
    get_live_task_ids,
    requeue_abandoned_jobs,
)


class TestEnqueueWorkflow:
    def test_enqueues_a_workflow_with_one_rq_retry(self):
        with patch("demetra.services.persistence.queue.queue.enqueue") as mock_enqueue:
            enqueue_workflow(project_name="demetra", task_id="CH-1")

        mock_enqueue.assert_called_once_with(WORKFLOW_JOB_PATH, project_name="demetra", task_id="CH-1", retry=ANY)
        assert mock_enqueue.call_args.kwargs["retry"].max == 1


class TestGetLiveTaskIds:
    @staticmethod
    def _registry(registry_class, job_ids: list[str], expired_job_ids: list[str] | None = None):
        registry = registry_class.return_value
        registry.get_job_ids.return_value = job_ids
        registry.get_expired_job_ids.return_value = expired_job_ids or []
        return registry

    def test_returns_the_task_id_of_every_running_job(self):
        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch(
                "demetra.services.persistence.queue.Job.fetch_many",
                return_value=[
                    SimpleNamespace(kwargs={"project_name": "demetra", "task_id": "CH-1"}),
                    SimpleNamespace(kwargs={"project_name": "demetra", "task_id": "6b0b0f6e-1a2b-4c3d-8e9f"}),
                ],
            ) as fetch,
        ):
            self._registry(registry_class, job_ids=["job-1", "job-2"])

            assert get_live_task_ids() == ["CH-1", "6b0b0f6e-1a2b-4c3d-8e9f"]

        fetch.assert_called_once_with(job_ids=["job-1", "job-2"], connection=ANY)

    def test_skips_the_registry_entries_whose_expiry_has_passed(self):
        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch(
                "demetra.services.persistence.queue.Job.fetch_many",
                return_value=[SimpleNamespace(kwargs={"task_id": "CH-2"})],
            ) as fetch,
        ):
            self._registry(registry_class, job_ids=["job-1", "job-2"], expired_job_ids=["job-1"])

            assert get_live_task_ids() == ["CH-2"]

        fetch.assert_called_once_with(job_ids=["job-2"], connection=ANY)

    def test_reads_the_registry_without_cleaning_it_up(self):
        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.Job.fetch_many", return_value=[]),
        ):
            registry = self._registry(registry_class, job_ids=[])

            get_live_task_ids()

        registry.get_job_ids.assert_called_once_with(cleanup=False)
        registry.cleanup.assert_not_called()

    def test_returns_an_empty_list_when_the_registry_has_no_live_entries(self):
        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.Job.fetch_many", return_value=[]) as fetch,
        ):
            self._registry(registry_class, job_ids=[])

            assert get_live_task_ids() == []

        fetch.assert_called_once_with(job_ids=[], connection=ANY)

    def test_preserves_the_registry_order_of_the_task_ids(self):
        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch(
                "demetra.services.persistence.queue.Job.fetch_many",
                return_value=[
                    SimpleNamespace(kwargs={"task_id": "CH-2"}),
                    SimpleNamespace(kwargs={"task_id": "CH-1"}),
                ],
            ),
        ):
            self._registry(registry_class, job_ids=["job-2", "job-1"])

            assert get_live_task_ids() == ["CH-2", "CH-1"]

    def test_skips_missing_jobs_and_jobs_without_a_task_id(self):
        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch(
                "demetra.services.persistence.queue.Job.fetch_many",
                return_value=[
                    None,
                    SimpleNamespace(kwargs={"project_name": "demetra"}),
                    SimpleNamespace(kwargs={"task_id": ""}),
                    SimpleNamespace(kwargs={"task_id": "CH-7"}),
                ],
            ),
        ):
            self._registry(registry_class, job_ids=["job-1", "job-2", "job-3", "job-4"])

            assert get_live_task_ids() == ["CH-7"]

    def test_returns_an_empty_list_when_the_broker_is_unreachable(self):
        with patch(
            "demetra.services.persistence.queue.StartedJobRegistry",
            side_effect=RedisError("connection refused"),
        ):
            assert get_live_task_ids() == []


class TestRequeueAbandonedJobs:
    @staticmethod
    def _snapshot(
        registry_class, connection_class_mock, entries: list[tuple[str, float]]
    ) -> tuple[MagicMock, MagicMock]:
        registry = registry_class.return_value
        registry.key = "rq:registry:started"
        registry.parse_job_id.side_effect = StartedJobRegistry.parse_job_id
        connection_class_mock.zrange.return_value = [(member.encode(), score) for member, score in entries]
        connection_class_mock.eval.return_value = []
        return registry, connection_class_mock

    @staticmethod
    def _claim(connection_class, members: list[str]) -> None:
        connection_class.eval.return_value = [member.encode() for member in members]

    def test_claims_only_expired_members_and_enqueues_each_of_their_jobs(self):
        jobs = {"job-1": MagicMock(), "job-2": MagicMock()}
        for job in jobs.values():
            job.get_status.return_value = JobStatus.STARTED

        def _fetch(**kwargs):
            return jobs[kwargs["id"]]

        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.connection") as connection_mock,
            patch("demetra.services.persistence.queue.Job.fetch", side_effect=_fetch) as mock_fetch,
            patch("demetra.services.persistence.queue.queue.enqueue_job") as mock_enqueue,
            patch("demetra.services.persistence.queue.current_timestamp", return_value=1000.0),
        ):
            registry, connection = self._snapshot(
                registry_class,
                connection_class_mock=connection_mock,
                entries=[("job-1:exec-1", 900.0), ("job-2:exec-2", 950.0)],
            )
            self._claim(connection_class=connection_mock, members=["job-1:exec-1", "job-2:exec-2"])

            assert requeue_abandoned_jobs() == ["job-1", "job-2"]

        assert [call.kwargs["id"] for call in mock_fetch.call_args_list] == ["job-1", "job-2"]
        assert [call.args[0] for call in mock_enqueue.call_args_list] == [jobs["job-1"], jobs["job-2"]]
        connection.zrange.assert_called_once_with(name=registry.key, start=0, end=-1, withscores=True)
        connection.eval.assert_called_once_with(
            REMOVE_EXPIRED_MEMBERS_SCRIPT, 1, registry.key, 1000.0, b"job-1:exec-1", b"job-2:exec-2"
        )
        connection.zrem.assert_not_called()
        registry.remove_executions.assert_not_called()
        registry.requeue.assert_not_called()
        for job in jobs.values():
            assert job.started_at is None
            assert job.ended_at is None
            job.save.assert_called_once_with()

    def test_claims_a_stale_member_even_when_the_job_no_longer_exists(self):
        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.connection") as connection_mock,
            patch("demetra.services.persistence.queue.Job.fetch", side_effect=NoSuchJobError("gone")),
            patch("demetra.services.persistence.queue.queue.enqueue_job") as mock_enqueue,
        ):
            _, connection = self._snapshot(
                registry_class, connection_class_mock=connection_mock, entries=[("job-1:exec-1", 900.0)]
            )
            self._claim(connection_class=connection_mock, members=["job-1:exec-1"])

            assert requeue_abandoned_jobs() == []

        mock_enqueue.assert_not_called()
        connection.zadd.assert_not_called()

    def test_ignores_an_unparseable_registry_member(self):
        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.connection") as connection_mock,
            patch("demetra.services.persistence.queue.Job.fetch") as mock_fetch,
        ):
            registry, connection = self._snapshot(
                registry_class, connection_class_mock=connection_mock, entries=[("job-1:exec-1:extra", 900.0)]
            )
            registry.parse_job_id.side_effect = ValueError("bad composite key")

            assert requeue_abandoned_jobs() == []

        mock_fetch.assert_not_called()
        connection.eval.assert_not_called()

    def test_leaves_a_member_that_was_renewed_before_the_claim(self):
        job = MagicMock()
        job.get_status.return_value = JobStatus.STARTED

        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.connection") as connection_mock,
            patch("demetra.services.persistence.queue.Job.fetch", return_value=job),
            patch("demetra.services.persistence.queue.queue.enqueue_job") as mock_enqueue,
        ):
            _, connection = self._snapshot(
                registry_class, connection_class_mock=connection_mock, entries=[("job-1:exec-1", 900.0)]
            )

            assert requeue_abandoned_jobs() == []

        mock_enqueue.assert_not_called()
        connection.eval.assert_called_once()
        connection.zadd.assert_not_called()
        assert job.get_status.call_count == 1

    def test_claims_a_stale_member_without_enqueueing_an_already_queued_job(self):
        job = MagicMock()
        job.get_status.return_value = JobStatus.QUEUED

        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.connection") as connection_mock,
            patch("demetra.services.persistence.queue.Job.fetch", return_value=job),
            patch("demetra.services.persistence.queue.queue.enqueue_job") as mock_enqueue,
        ):
            _, connection = self._snapshot(
                registry_class, connection_class_mock=connection_mock, entries=[("job-1:exec-1", 900.0)]
            )
            self._claim(connection_class=connection_mock, members=["job-1:exec-1"])

            assert requeue_abandoned_jobs() == []

        connection.eval.assert_called_once()
        mock_enqueue.assert_not_called()

    def test_claims_a_stale_member_when_a_fresh_worker_started_the_job_again(self):
        job = MagicMock()
        job.get_status.return_value = JobStatus.STARTED

        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.connection") as connection_mock,
            patch("demetra.services.persistence.queue.Job.fetch", return_value=job),
            patch("demetra.services.persistence.queue.queue.enqueue_job") as mock_enqueue,
            patch("demetra.services.persistence.queue.current_timestamp", return_value=1000.0),
        ):
            _, connection = self._snapshot(
                registry_class,
                connection_class_mock=connection_mock,
                entries=[("job-1:exec-1", 900.0), ("job-1:exec-2", 1100.0)],
            )
            self._claim(connection_class=connection_mock, members=["job-1:exec-1"])

            assert requeue_abandoned_jobs() == []

        mock_enqueue.assert_not_called()
        assert connection.eval.call_args.args[4:] == (b"job-1:exec-1",)

    def test_an_enqueue_failure_does_not_orphan_members_processed_before_it(self):
        jobs = {"job-1": MagicMock(), "job-2": MagicMock()}
        for job in jobs.values():
            job.get_status.return_value = JobStatus.STARTED

        def _fetch(**kwargs):
            return jobs[kwargs["id"]]

        def _enqueue(job):
            if job is jobs["job-2"]:
                raise RedisError("connection lost")

        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.connection") as connection_mock,
            patch("demetra.services.persistence.queue.Job.fetch", side_effect=_fetch),
            patch("demetra.services.persistence.queue.queue.enqueue_job", side_effect=_enqueue),
        ):
            _, connection = self._snapshot(
                registry_class,
                connection_class_mock=connection_mock,
                entries=[("job-1:exec-1", 900.0), ("job-2:exec-2", 950.0)],
            )
            self._claim(connection_class=connection_mock, members=["job-1:exec-1", "job-2:exec-2"])

            assert requeue_abandoned_jobs() == ["job-1"]

        connection.zadd.assert_called_once_with(connection.eval.call_args.args[2], {"job-2:exec-2": 950.0})

    def test_restores_a_claimed_member_when_the_job_state_cannot_be_saved(self):
        job = MagicMock()
        job.get_status.return_value = JobStatus.STARTED
        job.save.side_effect = RedisError("connection lost")

        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.connection") as connection_mock,
            patch("demetra.services.persistence.queue.Job.fetch", return_value=job),
            patch("demetra.services.persistence.queue.queue.enqueue_job") as mock_enqueue,
        ):
            _, connection = self._snapshot(
                registry_class, connection_class_mock=connection_mock, entries=[("job-1:exec-1", 900.0)]
            )
            self._claim(connection_class=connection_mock, members=["job-1:exec-1"])

            assert requeue_abandoned_jobs() == []

        mock_enqueue.assert_not_called()
        connection.zadd.assert_called_once_with(connection.eval.call_args.args[2], {"job-1:exec-1": 900.0})

    def test_treats_a_member_expiring_exactly_now_as_expired_not_active(self):
        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.connection") as connection_mock,
            patch("demetra.services.persistence.queue.current_timestamp", return_value=1000.0),
            patch("demetra.services.persistence.queue.Job.fetch", side_effect=NoSuchJobError("gone")),
        ):
            registry, connection = self._snapshot(
                registry_class,
                connection_class_mock=connection_mock,
                entries=[("job-1:exec-1", 1000.0), ("job-2:exec-2", 1001.0)],
            )
            self._claim(connection_class=connection_mock, members=["job-1:exec-1"])

            assert requeue_abandoned_jobs() == []

        assert connection.eval.call_args.args[2:] == (registry.key, 1000.0, b"job-1:exec-1")
        connection.zrange.assert_called_once_with(name=registry.key, start=0, end=-1, withscores=True)
        connection.zrangebyscore.assert_not_called()

    def test_returns_an_empty_list_when_the_broker_is_unreachable(self):
        with patch(
            "demetra.services.persistence.queue.StartedJobRegistry",
            side_effect=RedisError("connection refused"),
        ):
            assert requeue_abandoned_jobs() == []

    def test_returns_an_empty_list_when_the_claim_fails(self):
        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.connection") as connection_mock,
            patch("demetra.services.persistence.queue.Job.fetch", side_effect=NoSuchJobError("gone")),
        ):
            _, connection = self._snapshot(
                registry_class, connection_class_mock=connection_mock, entries=[("job-1:exec-1", 900.0)]
            )
            connection.eval.side_effect = RedisError("connection lost")

            assert requeue_abandoned_jobs() == []
