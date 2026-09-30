from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from demetra.library.exceptions import EnvironmentConfigError
from demetra.library.models import Context, LinearTask, Project, SessionEnvironment
from demetra.services import tracker


def _linear_env() -> SessionEnvironment:
    return SessionEnvironment(project_environment={}, user_environment={})


def _clickup_env() -> SessionEnvironment:
    return SessionEnvironment(project_environment={"ISSUE_TRACKER": "clickup"}, user_environment={})


def _context(faker, environment: SessionEnvironment) -> Context:
    return Context(
        project=Project(
            id="project-1",
            user_id="user-1",
            linear_project_id="list-1",
            name="demetra",
            state="active",
            repository_url="https://github.com/test/demetra",
            repository_name="demetra",
            repository_owner="test",
            local_path=Path(f"/tmp/{faker.slug()}"),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        ),
        auto_mode=True,
        linear_task=LinearTask(
            id=str(uuid4()),
            identifier="MNT-1",
            title="t",
            description="d",
            priority=1,
            created_at=datetime.now().isoformat(),
        ),
        branch_name="b",
        worktree_path=Path("/tmp/w"),
        session=None,
        _environment=environment,
    )


@pytest.fixture(autouse=True)
def settings_default_tracker():
    with patch("demetra.settings.ISSUE_TRACKER", "linear"):
        yield


class TestTrackerResolution:
    def test_defaults_to_linear_from_settings(self):
        assert tracker.is_clickup(None) is False
        assert tracker.resolve_environment(None).issue_tracker == "linear"

    def test_project_layer_selects_clickup(self):
        assert tracker.is_clickup(_clickup_env()) is True

    def test_user_layer_selects_clickup(self):
        environment = SessionEnvironment(project_environment={}, user_environment={"ISSUE_TRACKER": "clickup"})
        assert tracker.is_clickup(environment) is True

    def test_settings_layer_selects_clickup(self):
        with patch("demetra.settings.ISSUE_TRACKER", "clickup"):
            assert tracker.is_clickup(None) is True

    def test_unknown_tracker_raises(self):
        environment = SessionEnvironment(project_environment={"ISSUE_TRACKER": "jira"}, user_environment={})
        with pytest.raises(EnvironmentConfigError, match="ISSUE_TRACKER"):
            tracker.is_clickup(environment)

    def test_research_labels_follow_the_tracker(self):
        with (
            patch("demetra.services.tracker.LINEAR", {"research_labels": ["Research"]}),
            patch("demetra.services.tracker.CLICKUP", {"research_labels": ["research", "spike"]}),
        ):
            assert tracker.research_labels(_linear_env()) == ["Research"]
            assert tracker.research_labels(_clickup_env()) == ["research", "spike"]

    @pytest.mark.asyncio
    async def test_load_environment_merges_project_and_user_layers(self):
        with (
            patch(
                "demetra.services.tracker.get_user_environments_decrypted",
                new_callable=AsyncMock,
                return_value={"ISSUE_TRACKER": "clickup"},
            ) as user_mock,
            patch(
                "demetra.services.tracker.get_project_environments",
                new_callable=AsyncMock,
                return_value={"CLICKUP_TEAM_ID": "team-9"},
            ) as project_mock,
        ):
            environment = await tracker.load_environment(user_id="user-1", project_id="project-1")

        user_mock.assert_awaited_once_with(user_id="user-1")
        project_mock.assert_awaited_once_with(project_id="project-1")
        assert environment.issue_tracker == "clickup"
        assert environment.clickup_value("team_id") == "team-9"


class TestTrackerDispatch:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("facade", "linear_name", "clickup_name", "kwargs"),
        [
            ("get_task_by_id", "get_linear_task_by_id", "get_clickup_task_by_id", {"task_id": "t-1"}),
            ("update_ticket_status", "update_ticket_status", "update_ticket_status", {"task_id": "t", "state_id": "s"}),
            ("post_comment", "post_comment", "post_comment", {"task_id": "t", "body": "b"}),
        ],
    )
    async def test_dispatches_on_environment(self, facade, linear_name, clickup_name, kwargs):
        with (
            patch(f"demetra.services.tracker.linear_service.{linear_name}", new_callable=AsyncMock) as linear_mock,
            patch(f"demetra.services.tracker.clickup_service.{clickup_name}", new_callable=AsyncMock) as clickup_mock,
        ):
            await getattr(tracker, facade)(**kwargs, environment=_clickup_env())
            clickup_mock.assert_awaited_once_with(**kwargs)
            linear_mock.assert_not_awaited()

            clickup_mock.reset_mock()
            await getattr(tracker, facade)(**kwargs, environment=_linear_env())
            linear_mock.assert_awaited_once_with(**kwargs)
            clickup_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_environment_defaults_to_settings_tracker(self):
        with (
            patch("demetra.services.tracker.linear_service.post_comment", new_callable=AsyncMock) as linear_mock,
            patch("demetra.services.tracker.clickup_service.post_comment", new_callable=AsyncMock) as clickup_mock,
        ):
            await tracker.post_comment(task_id="t", body="b")
            linear_mock.assert_awaited_once()
            clickup_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_todo_issues_loads_user_environment_to_pick_tracker(self):
        with (
            patch(
                "demetra.services.tracker.get_user_environments_decrypted",
                new_callable=AsyncMock,
                return_value={"ISSUE_TRACKER": "clickup"},
            ),
            patch("demetra.services.tracker.linear_service.get_todo_issues", new_callable=AsyncMock) as linear_mock,
            patch("demetra.services.tracker.clickup_service.get_todo_issues", new_callable=AsyncMock) as clickup_mock,
        ):
            await tracker.get_todo_issues(project_name="demetra", user_id="user-1")

        clickup_mock.assert_awaited_once()
        assert clickup_mock.await_args_list[0].kwargs["project_name"] == "demetra"
        assert clickup_mock.await_args_list[0].kwargs["environment"].issue_tracker == "clickup"
        linear_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_task_dispatches_with_explicit_environment(self):
        with (
            patch("demetra.services.tracker.linear_service.get_linear_task", new_callable=AsyncMock) as linear_mock,
            patch("demetra.services.tracker.clickup_service.get_clickup_task", new_callable=AsyncMock) as clickup_mock,
        ):
            environment = _linear_env()
            await tracker.get_task(project_name="demetra", user_id="user-1", environment=environment)

        linear_mock.assert_awaited_once_with(project_name="demetra", user_id="user-1", environment=environment)
        clickup_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_ticket_dispatches(self):
        with (
            patch(
                "demetra.services.tracker.linear_service.create_linear_ticket", new_callable=AsyncMock
            ) as linear_mock,
            patch(
                "demetra.services.tracker.clickup_service.create_clickup_ticket", new_callable=AsyncMock
            ) as clickup_mock,
        ):
            await tracker.create_ticket("T", "D", "R", "A", environment=_clickup_env())
            clickup_mock.assert_awaited_once_with(
                title="T", description="D", technical_requirements="R", acceptance_criteria="A", user_id=None
            )
            linear_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_research_ticket_and_cleanup_use_context_environment(self, faker):
        context = _context(faker, environment=_clickup_env())
        with (
            patch(
                "demetra.services.tracker.clickup_service.create_research_ticket", new_callable=AsyncMock
            ) as create_mock,
            patch("demetra.services.tracker.clickup_service.clickup_cleanup", new_callable=AsyncMock) as cleanup_mock,
            patch(
                "demetra.services.tracker.linear_service.create_research_ticket", new_callable=AsyncMock
            ) as lin_create,
            patch("demetra.services.tracker.linear_service.linear_cleanup", new_callable=AsyncMock) as lin_cleanup,
        ):
            await tracker.create_research_ticket(context=context, report="r")
            await tracker.tracker_cleanup(context=context, is_success=True)

        create_mock.assert_awaited_once_with(context=context, report="r", title=None)
        cleanup_mock.assert_awaited_once_with(context=context, is_success=True)
        lin_create.assert_not_awaited()
        lin_cleanup.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_linear_context_routes_cleanup_to_linear(self, faker):
        context = _context(faker, environment=_linear_env())
        with (
            patch("demetra.services.tracker.clickup_service.clickup_cleanup", new_callable=AsyncMock) as cleanup_mock,
            patch("demetra.services.tracker.linear_service.linear_cleanup", new_callable=AsyncMock) as lin_cleanup,
        ):
            await tracker.tracker_cleanup(context=context, is_success=False)

        lin_cleanup.assert_awaited_once_with(context=context, is_success=False)
        cleanup_mock.assert_not_awaited()
