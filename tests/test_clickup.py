from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import aiohttp
import pytest

from demetra.library.exceptions import ClickUpConfigError, ClickUpError, TrackerConfigError, TrackerError
from demetra.library.models import Context, LinearTask, Project, SessionEnvironment
from demetra.services.clickup import (
    build_task,
    clickup_cleanup,
    create_clickup_ticket,
    create_research_ticket,
    extract_comments,
    extract_labels,
    fetch_task_comments,
    get_clickup_task,
    get_clickup_task_by_id,
    get_todo_issues,
    parse_created_at,
    parse_priority,
    post_comment,
    update_ticket_status,
)
from demetra.services.clickup.api import clickup_request


CLICKUP_SETTINGS: dict = {
    "api_url": "https://api.clickup.com/api/v2",
    "api_token": "pk_test_token",
    "team_id": "team-1",
    "list_id": "list-default",
    "service_name": "clickup",
    "feature_tag": "feature",
    "backend_tag": "backend",
    "frontend_tag": "frontend",
    "states": {
        "prd": "prd",
        "todo": "to do",
        "in_progress": "in progress",
        "in_review": "in review",
        "awaiting_input": "awaiting input",
        "done": "complete",
    },
    "default_state": "prd",
    "filter_labels": [],
    "research_labels": ["Research"],
}


def _clickup_environment(**project_env) -> SessionEnvironment:
    return SessionEnvironment(project_environment={"ISSUE_TRACKER": "clickup", **project_env}, user_environment={})


def _raw_task(**overrides) -> dict:
    task = {
        "id": f"task-{uuid4().hex[:8]}",
        "custom_id": "MNT-42",
        "name": "Add ClickUp support",
        "description": "plain description",
        "markdown_description": "**markdown** description",
        "status": {"status": "to do", "type": "open"},
        "priority": {"id": "2", "priority": "high"},
        "date_created": "1759240800000",
        "url": "https://app.clickup.com/t/task-1",
        "list": {"id": "LIST-1", "name": "Demetra"},
        "tags": [{"name": "backend"}, {"name": "Research"}],
    }
    task.update(overrides)
    return task


def _context(faker, *, labels=None, list_id="list-1", priority=1) -> Context:
    return Context(
        project=Project(
            id=str(uuid4()),
            user_id=str(uuid4()),
            linear_project_id=list_id,
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
            id="task-1",
            identifier="MNT-42",
            title="Add ClickUp support",
            description="desc",
            priority=priority,
            created_at=datetime.now().isoformat(),
            labels=labels or [],
            linear_project_id=list_id,
        ),
        branch_name="mnt-42-add-clickup-support",
        worktree_path=Path(f"/tmp/{faker.slug()}"),
        session=None,
        _environment=_clickup_environment(),
    )


@pytest.fixture
def clickup_settings():
    with (
        patch("demetra.settings.CLICKUP", CLICKUP_SETTINGS),
        patch("demetra.services.clickup.CLICKUP", CLICKUP_SETTINGS),
        patch("demetra.services.clickup.api.CLICKUP", CLICKUP_SETTINGS),
    ):
        yield CLICKUP_SETTINGS


@pytest.fixture
def mock_request():
    with patch("demetra.services.clickup.clickup_request", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_linked_projects():
    with patch("demetra.services.clickup.get_linked_projects", new_callable=AsyncMock) as mock:
        mock.return_value = {"list-1": ("project-1", "user-1"), "demetra": ("project-1", "user-1")}
        yield mock


@pytest.fixture(autouse=True)
def mock_print_message():
    with patch("demetra.services.clickup.print_message"):
        yield


@pytest.fixture(autouse=True)
def mock_user_environment():
    with patch("demetra.services.clickup.get_user_environments_decrypted", new_callable=AsyncMock, return_value={}):
        yield


class TestClickUpRequest:
    @pytest.mark.asyncio
    async def test_raises_config_error_without_token(self):
        with patch("demetra.services.clickup.api.CLICKUP", {**CLICKUP_SETTINGS, "api_token": None}):
            with pytest.raises(ClickUpConfigError, match="CLICKUP_API_TOKEN"):
                await clickup_request(method="GET", path="/task/1")

    @pytest.mark.asyncio
    async def test_sends_token_verbatim_and_returns_payload(self, clickup_settings):
        response = MagicMock()
        response.status = 200
        response.json = AsyncMock(return_value={"id": "task-1"})
        response.__aenter__ = AsyncMock(return_value=response)
        response.__aexit__ = AsyncMock(return_value=None)
        session = MagicMock()
        session.request = MagicMock(return_value=response)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch("demetra.services.clickup.api.aiohttp.ClientSession", return_value=session):
            result = await clickup_request(method="GET", path="/task/task-1", params={"a": "b"})

        assert result == {"id": "task-1"}
        args, kwargs = session.request.call_args
        assert args == ("GET", "https://api.clickup.com/api/v2/task/task-1")
        assert kwargs["headers"]["Authorization"] == "pk_test_token"
        assert kwargs["params"] == {"a": "b"}

    @pytest.mark.asyncio
    async def test_http_error_status_raises_clickup_error(self, clickup_settings):
        response = MagicMock()
        response.status = 401
        response.text = AsyncMock(return_value="Token invalid")
        response.__aenter__ = AsyncMock(return_value=response)
        response.__aexit__ = AsyncMock(return_value=None)
        session = MagicMock()
        session.request = MagicMock(return_value=response)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch("demetra.services.clickup.api.aiohttp.ClientSession", return_value=session):
            with pytest.raises(ClickUpError, match="401"):
                await clickup_request(method="GET", path="/task/task-1")

    @pytest.mark.asyncio
    async def test_client_error_is_wrapped(self, clickup_settings):
        session = MagicMock()
        session.request = MagicMock(side_effect=aiohttp.ClientError("boom"))
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch("demetra.services.clickup.api.aiohttp.ClientSession", return_value=session):
            with pytest.raises(ClickUpError, match="boom"):
                await clickup_request(method="GET", path="/task/task-1")

    def test_error_hierarchy_maps_onto_tracker_errors(self):
        assert issubclass(ClickUpError, TrackerError)
        assert issubclass(ClickUpConfigError, TrackerConfigError)
        assert issubclass(ClickUpConfigError, ClickUpError)


class TestClickUpParsing:
    def test_extract_labels_reads_tag_names(self):
        assert extract_labels(_raw_task()) == ["backend", "Research"]
        assert extract_labels({"tags": None}) == []

    def test_extract_comments_skips_resolved_and_orders_oldest_first(self):
        comments = [
            {"id": "3", "comment_text": "newest", "resolved": False, "reply_count": "0"},
            {"id": "2", "comment_text": "resolved", "resolved": True, "reply_count": "0"},
            {"id": "1", "comment_text": "oldest", "resolved": False, "reply_count": "1"},
        ]
        replies = {"1": [{"comment_text": "reply-b"}, {"comment_text": "reply-a"}]}

        assert extract_comments(comments=comments, replies=replies) == ["oldest", "reply-a", "reply-b", "newest"]

    def test_parse_priority_handles_missing_and_invalid(self):
        assert parse_priority(_raw_task()) == 2
        assert parse_priority(_raw_task(priority=None)) == 0
        assert parse_priority(_raw_task(priority={"id": "urgent"})) == 0

    def test_parse_created_at_converts_millisecond_epoch(self):
        assert parse_created_at(_raw_task()).startswith("2025-09-30T")
        assert parse_created_at({}) == ""
        assert parse_created_at({"date_created": "not-a-number"}) == ""

    def test_build_task_maps_list_to_project_and_prefers_markdown(self):
        raw = _raw_task()
        linked = {"list-1": ("project-1", "user-1")}

        task = build_task(task=raw, linked_projects=linked, comments=["c1"])

        assert task.id == raw["id"]
        assert task.identifier == "MNT-42"
        assert task.description == "**markdown** description"
        assert task.priority == 2
        assert task.state == "to do"
        assert task.project_name == "demetra"
        assert task.project_id == "project-1"
        assert task.user_id == "user-1"
        assert task.linear_project_id == "list-1"
        assert task.comments == ["c1"]
        assert task.labels == ["backend", "Research"]
        assert task.url == "https://app.clickup.com/t/task-1"

    def test_build_task_falls_back_to_id_when_no_custom_id(self):
        task = build_task(task=_raw_task(custom_id=None, id="abc"), linked_projects={}, comments=[])
        assert task.identifier == "abc"
        assert task.project_id is None


class TestClickUpTasks:
    @pytest.mark.asyncio
    async def test_fetch_task_comments_expands_threads(self, mock_request):
        mock_request.side_effect = [
            {"comments": [{"id": "9", "comment_text": "root", "resolved": False, "reply_count": "1"}]},
            {"comments": [{"id": "10", "comment_text": "reply", "resolved": False, "reply_count": "0"}]},
        ]

        result = await fetch_task_comments(task_id="task-1")

        assert result == ["root", "reply"]
        assert mock_request.await_args_list[0].kwargs["path"] == "/task/task-1/comment"
        assert mock_request.await_args_list[1].kwargs["path"] == "/comment/9/reply"

    @pytest.mark.asyncio
    async def test_get_todo_issues_filters_by_list_name_and_tags(
        self, clickup_settings, mock_request, mock_linked_projects
    ):
        matching = _raw_task(id="t1")
        other_list = _raw_task(id="t2", list={"id": "list-2", "name": "Other"})
        no_list = _raw_task(id="t3", list={})
        mock_request.side_effect = [
            {"tasks": [matching, other_list, no_list], "last_page": True},
            {"comments": []},
        ]

        tasks = await get_todo_issues(project_name="Demetra", environment=_clickup_environment())

        assert [task.id for task in tasks] == ["t1"]
        first_call = mock_request.await_args_list[0]
        assert first_call.kwargs["path"] == "/team/team-1/task"
        assert ("statuses[]", "to do") in first_call.kwargs["params"]
        assert ("page", 0) in first_call.kwargs["params"]

    @pytest.mark.asyncio
    async def test_get_todo_issues_applies_filter_labels(self, clickup_settings, mock_request, mock_linked_projects):
        mock_request.side_effect = [
            {"tasks": [_raw_task(id="t1", tags=[{"name": "bug"}]), _raw_task(id="t2")], "last_page": True},
            {"comments": []},
        ]

        with patch("demetra.services.clickup.CLICKUP", {**CLICKUP_SETTINGS, "filter_labels": ["backend"]}):
            tasks = await get_todo_issues(environment=_clickup_environment())

        assert [task.id for task in tasks] == ["t2"]

    @pytest.mark.asyncio
    async def test_get_todo_issues_pages_until_last_page(self, clickup_settings, mock_request, mock_linked_projects):
        mock_request.side_effect = [
            {"tasks": [_raw_task(id="t1")], "last_page": False},
            {"tasks": [_raw_task(id="t2")], "last_page": True},
            {"comments": []},
            {"comments": []},
        ]

        tasks = await get_todo_issues(environment=_clickup_environment())

        assert [task.id for task in tasks] == ["t1", "t2"]
        assert ("page", 1) in mock_request.await_args_list[1].kwargs["params"]

    @pytest.mark.asyncio
    async def test_get_todo_issues_requires_team_id(self, mock_request):
        with patch("demetra.settings.CLICKUP", {**CLICKUP_SETTINGS, "team_id": None}):
            with pytest.raises(ClickUpConfigError, match="CLICKUP_TEAM_ID"):
                await get_todo_issues(environment=_clickup_environment())

        mock_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_todo_issues_reads_team_id_from_environment_layer(
        self, clickup_settings, mock_request, mock_linked_projects
    ):
        mock_request.side_effect = [{"tasks": [], "last_page": True}]

        await get_todo_issues(environment=_clickup_environment(CLICKUP_TEAM_ID="team-override"))

        assert mock_request.await_args.kwargs["path"] == "/team/team-override/task"

    @pytest.mark.asyncio
    async def test_get_clickup_task_by_id_returns_none_when_missing(self, mock_request, mock_linked_projects):
        mock_request.return_value = {"err": "Task not found"}

        assert await get_clickup_task_by_id(task_id="missing") is None

    @pytest.mark.asyncio
    async def test_get_clickup_task_by_id_builds_task_with_comments(self, mock_request, mock_linked_projects):
        mock_request.side_effect = [
            _raw_task(id="task-1"),
            {"comments": [{"id": "1", "comment_text": "hello", "resolved": False, "reply_count": "0"}]},
        ]

        task = await get_clickup_task_by_id(task_id="task-1")

        assert task is not None
        assert task.id == "task-1"
        assert task.comments == ["hello"]
        assert mock_request.await_args_list[0].kwargs["params"] == {"include_markdown_description": "true"}

    @pytest.mark.asyncio
    async def test_get_clickup_task_picks_highest_priority(self, clickup_settings, mock_request, mock_linked_projects):
        low = _raw_task(id="low", priority={"id": "4"}, date_created="1759240800000")
        high = _raw_task(id="high", priority={"id": "1"}, date_created="1759240800000")
        mock_request.side_effect = [
            {"tasks": [low, high], "last_page": True},
            {"comments": []},
            {"comments": []},
        ]

        task = await get_clickup_task(project_name="demetra", environment=_clickup_environment())

        assert task is not None
        assert task.id == "high"


class TestClickUpMutations:
    @pytest.mark.asyncio
    async def test_update_ticket_status_puts_status_and_confirms(self, mock_request):
        mock_request.return_value = {"id": "task-1", "status": {"status": "In Review"}}

        assert await update_ticket_status(task_id="task-1", state_id="in review") is True
        assert mock_request.await_args.kwargs == {
            "method": "PUT",
            "path": "/task/task-1",
            "json": {"status": "in review"},
        }

    @pytest.mark.asyncio
    async def test_update_ticket_status_false_when_status_not_applied(self, mock_request):
        mock_request.return_value = {"id": "task-1", "status": {"status": "to do"}}

        assert await update_ticket_status(task_id="task-1", state_id="in review") is False

    @pytest.mark.asyncio
    async def test_post_comment_returns_true_on_id(self, mock_request):
        mock_request.return_value = {"id": "comment-1"}

        assert await post_comment(task_id="task-1", body="## Plan") is True
        assert mock_request.await_args.kwargs["json"] == {"comment_text": "## Plan", "notify_all": False}

    @pytest.mark.asyncio
    async def test_post_comment_returns_false_without_id(self, mock_request):
        mock_request.return_value = {}

        assert await post_comment(task_id="task-1", body="x") is False

    @pytest.mark.asyncio
    async def test_cleanup_success_moves_to_in_review(self, faker, clickup_settings):
        context = _context(faker)
        with patch("demetra.services.clickup.update_ticket_status", new_callable=AsyncMock) as mock_update:
            await clickup_cleanup(context=context, is_success=True)

        mock_update.assert_awaited_once_with(task_id="task-1", state_id="in review")

    @pytest.mark.asyncio
    async def test_cleanup_failure_moves_to_todo(self, faker, clickup_settings):
        context = _context(faker)
        with patch("demetra.services.clickup.update_ticket_status", new_callable=AsyncMock) as mock_update:
            await clickup_cleanup(context=context, is_success=False)

        mock_update.assert_awaited_once_with(task_id="task-1", state_id="to do")

    @pytest.mark.asyncio
    async def test_create_ticket_uses_default_list_and_state(self, clickup_settings, mock_request):
        mock_request.return_value = {"id": "new-1", "custom_id": "MNT-100", "name": "Title"}

        result = await create_clickup_ticket("Title", "Desc", "Req", "AC")

        assert result == {"ticket_id": "new-1", "identifier": "MNT-100", "title": "Title"}
        call = mock_request.await_args.kwargs
        assert call["path"] == "/list/list-default/task"
        assert call["json"]["status"] == "prd"
        assert call["json"]["tags"] == ["feature"]
        assert "### Acceptance Criteria\nAC" in call["json"]["markdown_content"]

    @pytest.mark.asyncio
    async def test_create_ticket_requires_list_id(self, mock_request):
        with patch("demetra.settings.CLICKUP", {**CLICKUP_SETTINGS, "list_id": None}):
            with pytest.raises(ClickUpConfigError, match="list id"):
                await create_clickup_ticket("Title", "Desc", "Req", "AC")

        mock_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_ticket_raises_when_no_task_returned(self, clickup_settings, mock_request):
        mock_request.return_value = {"err": "bad"}

        with pytest.raises(ClickUpError, match="no task data"):
            await create_clickup_ticket("Title", "Desc", "Req", "AC")


class TestClickUpResearchTicket:
    @pytest.mark.asyncio
    async def test_creates_task_in_source_list_with_tags_and_priority(self, faker, clickup_settings, mock_request):
        context = _context(faker, labels=["Backend", "Research"], priority=2)
        mock_request.side_effect = [
            {"tasks": [], "last_page": True},
            {"id": "research-1", "custom_id": "MNT-43", "name": "Research: MNT-42 — Add ClickUp support"},
        ]

        result = await create_research_ticket(context=context, report="# Report")

        assert result["ticket_id"] == "research-1"
        create_call = mock_request.await_args_list[1].kwargs
        assert create_call["path"] == "/list/list-1/task"
        assert create_call["json"]["name"] == "Research: MNT-42 — Add ClickUp support"
        assert create_call["json"]["markdown_content"] == "# Report"
        assert create_call["json"]["status"] == "prd"
        assert create_call["json"]["tags"] == ["feature", "backend"]
        assert create_call["json"]["priority"] == 2

    @pytest.mark.asyncio
    async def test_reuses_existing_task_and_refreshes_description(self, faker, clickup_settings, mock_request):
        context = _context(faker)
        title = "Research: MNT-42 — Add ClickUp support"
        mock_request.side_effect = [
            {"tasks": [{"id": "existing-1", "custom_id": None, "name": title}], "last_page": True},
            {"id": "existing-1", "custom_id": None, "name": title},
        ]

        result = await create_research_ticket(context=context, report="# Updated")

        assert result == {"ticket_id": "existing-1", "identifier": "existing-1", "title": title}
        update_call = mock_request.await_args_list[1].kwargs
        assert update_call["method"] == "PUT"
        assert update_call["path"] == "/task/existing-1"
        assert update_call["json"] == {"markdown_content": "# Updated"}

    @pytest.mark.asyncio
    async def test_fails_permanently_without_source_list(self, faker, clickup_settings, mock_request):
        context = _context(faker, list_id=None)

        with pytest.raises(ClickUpConfigError, match="no list"):
            await create_research_ticket(context=context, report="# Report")

        mock_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_transient_api_failure_is_a_clickup_error(self, faker, clickup_settings, mock_request):
        context = _context(faker)
        mock_request.side_effect = [{"tasks": [], "last_page": True}, {"err": "rate limited"}]

        with pytest.raises(ClickUpError, match="Failed to create research"):
            await create_research_ticket(context=context, report="# Report")
