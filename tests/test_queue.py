from types import SimpleNamespace
from unittest.mock import ANY, patch

from redis.exceptions import RedisError

from demetra.services.persistence.queue import get_live_task_ids


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
