from types import SimpleNamespace
from unittest.mock import ANY, patch

from redis.exceptions import RedisError

from demetra.services.persistence.queue import (
    WORKFLOW_JOB_PATH,
    clear_pending_comments,
    enqueue_workflow,
    get_live_task_ids,
    load_pending_comments,
    requeue_abandoned_jobs,
    save_pending_comments,
    update_pending_comments,
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
                    SimpleNamespace(kwargs={"task_id": "6b0b0f6e-1a2b-4c3d-8e9f"}),
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


class TestPendingComments:
    PAYLOAD = {"pr_number": 42, "full_name": "owner/repo", "comments": [{"thread_id": "THREAD_1"}]}

    def test_save_is_conditional_and_expires(self):
        with patch("demetra.services.persistence.queue.connection") as mock_connection:
            mock_connection.set.return_value = True
            assert save_pending_comments("CH-1", self.PAYLOAD) is True
            assert mock_connection.set.call_args.kwargs["nx"] is True
            assert mock_connection.set.call_args.kwargs["ex"] > 0
            assert "CH-1" in mock_connection.set.call_args.kwargs["name"]

            mock_connection.set.return_value = None
            assert save_pending_comments("CH-1", self.PAYLOAD) is False

    def test_save_returns_none_on_redis_error(self):
        with patch("demetra.services.persistence.queue.connection") as mock_connection:
            mock_connection.set.side_effect = RedisError("connection refused")
            assert save_pending_comments("CH-1", self.PAYLOAD) is None

    def test_load_round_trips_payload(self):
        with patch("demetra.services.persistence.queue.connection") as mock_connection:
            mock_connection.set.return_value = True
            save_pending_comments("CH-1", self.PAYLOAD)
            mock_connection.get.return_value = mock_connection.set.call_args.kwargs["value"]
            assert load_pending_comments("CH-1") == self.PAYLOAD

    def test_load_returns_none_for_missing_corrupt_or_broken_payloads(self):
        with patch("demetra.services.persistence.queue.connection") as mock_connection:
            mock_connection.get.return_value = None
            assert load_pending_comments("CH-1") is None
            mock_connection.get.return_value = "not json"
            assert load_pending_comments("CH-1") is None
            mock_connection.get.return_value = b'["not", "a", "dict"]'
            assert load_pending_comments("CH-1") is None
            mock_connection.get.side_effect = RedisError("connection refused")
            assert load_pending_comments("CH-1") is None

    def test_clear_deletes_only_the_loaded_batch(self):
        with patch("demetra.services.persistence.queue.connection") as mock_connection:
            clear_pending_comments("CH-1", self.PAYLOAD)
            args = mock_connection.eval.call_args.args
            assert args[1:] == (
                1,
                "demetra:pending-comments:CH-1",
                '{"comments": [{"thread_id": "THREAD_1"}], "full_name": "owner/repo", "pr_number": 42}',
            )
            assert "redis.call('GET', KEYS[1])" in args[0]

    def test_clear_ignores_redis_errors(self):
        with patch("demetra.services.persistence.queue.connection") as mock_connection:
            mock_connection.eval.side_effect = RedisError("connection refused")
            clear_pending_comments("CH-1", self.PAYLOAD)

    def test_update_replaces_only_the_loaded_batch(self):
        with patch("demetra.services.persistence.queue.connection") as mock_connection:
            mock_connection.eval.return_value = "OK"
            updated = update_pending_comments("CH-1", self.PAYLOAD, {"attempt": 1})
            assert updated == {**self.PAYLOAD, "attempt": 1}
            args = mock_connection.eval.call_args.args
            assert args[3] == '{"comments": [{"thread_id": "THREAD_1"}], "full_name": "owner/repo", "pr_number": 42}'
            assert '"attempt": 1' in args[4]

    def test_update_returns_none_when_the_batch_changed(self):
        with patch("demetra.services.persistence.queue.connection") as mock_connection:
            mock_connection.eval.return_value = 0
            assert update_pending_comments("CH-1", self.PAYLOAD, {"attempt": 1}) is None

    def test_update_returns_none_on_redis_error(self):
        with patch("demetra.services.persistence.queue.connection") as mock_connection:
            mock_connection.eval.side_effect = OSError("connection refused")
            assert update_pending_comments("CH-1", self.PAYLOAD, {"attempt": 1}) is None


class TestRequeueAbandonedJobs:
    def test_delegates_expired_entries_to_the_standard_rq_cleanup(self):
        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.current_timestamp", return_value=1000.0),
            patch("demetra.services.persistence.queue.queue.enqueue_job") as mock_enqueue,
        ):
            registry = registry_class.return_value
            registry.get_expired_job_ids.return_value = ["job-1", "job-2"]

            assert requeue_abandoned_jobs() == ["job-1", "job-2"]

        registry_class.assert_called_once_with(queue=ANY, connection=ANY)
        registry.get_expired_job_ids.assert_called_once_with(timestamp=1000.0)
        registry.cleanup.assert_called_once_with(timestamp=1000.0)
        mock_enqueue.assert_not_called()

    def test_skips_cleanup_when_nothing_expired(self):
        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.current_timestamp", return_value=1000.0),
        ):
            registry = registry_class.return_value
            registry.get_expired_job_ids.return_value = []

            assert requeue_abandoned_jobs() == []

        registry.cleanup.assert_not_called()

    def test_returns_an_empty_list_when_the_expired_ids_cannot_be_read(self):
        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.current_timestamp", return_value=1000.0),
        ):
            registry = registry_class.return_value
            registry.get_expired_job_ids.side_effect = RedisError("connection refused")

            assert requeue_abandoned_jobs() == []

        registry.cleanup.assert_not_called()

    def test_returns_an_empty_list_when_cleanup_fails(self):
        with (
            patch("demetra.services.persistence.queue.StartedJobRegistry") as registry_class,
            patch("demetra.services.persistence.queue.current_timestamp", return_value=1000.0),
        ):
            registry = registry_class.return_value
            registry.get_expired_job_ids.return_value = ["job-1"]
            registry.cleanup.side_effect = RedisError("connection lost")

            assert requeue_abandoned_jobs() == []

    def test_returns_an_empty_list_when_the_registry_cannot_be_resolved(self):
        with patch(
            "demetra.services.persistence.queue.StartedJobRegistry",
            side_effect=OSError("connection refused"),
        ):
            assert requeue_abandoned_jobs() == []
