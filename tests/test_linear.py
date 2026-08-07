from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio

from demetra.library.exceptions import LinearError
from demetra.library.models import Context, LinearTask, Project
from demetra.library.tables import project_environments, projects
from demetra.services.linear import (
    create_linear_ticket,
    extract_comments,
    extract_labels,
    get_linear_task,
    get_linear_task_by_id,
    get_linked_projects,
    get_todo_issues,
    linear_cleanup,
    post_comment,
    update_ticket_status,
)
from demetra.services.persistence.database import (
    create_project,
)
from demetra.services.persistence.database import (
    get_connection as _get_connection,
)


class TestLinearService:
    @pytest.fixture
    def mock_linked(self, mock_linked_projects):
        with patch("demetra.services.linear.get_linked_projects", new_callable=AsyncMock) as m:
            m.return_value = mock_linked_projects
            yield m

    @pytest.fixture
    def mock_linear_settings(self):
        settings = {
            "team_id": "team-123",
            "default_state": "s1",
            "default_project": "p1",
            "feature_label_id": "l1",
            "states": {"todo": "state-todo"},
            "projects": {},
        }
        with patch("demetra.services.linear.LINEAR", settings):
            yield settings

    @pytest.mark.asyncio
    async def test_get_todo_issues_returns_matching_project(
        self,
        graphql_todo_issues_response_demetra: dict,
        mock_linked: AsyncMock,
        mock_linear_settings: dict,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_todo_issues_response_demetra

            issues = await get_todo_issues("demetra")

        assert len(issues) == 1
        assert issues[0].identifier.startswith("MNT-")
        assert issues[0].project_id is not None
        assert issues[0].user_id is not None

    @pytest.mark.asyncio
    async def test_get_todo_issues_filters_by_project_name(
        self,
        graphql_todo_issues_multiple_response_demetra: dict,
        mock_linked: AsyncMock,
        mock_linear_settings: dict,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_todo_issues_multiple_response_demetra

            issues = await get_todo_issues("demetra")

        assert len(issues) == 2

    @pytest.mark.asyncio
    async def test_get_linear_task_returns_first_by_priority(
        self,
        graphql_todo_issues_multiple_response_demetra: dict,
        mock_linked: AsyncMock,
        mock_linear_settings: dict,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_todo_issues_multiple_response_demetra

            task = await get_linear_task("demetra")

        assert task is not None

    @pytest.mark.asyncio
    async def test_get_linear_task_returns_none_when_no_issues(
        self,
        graphql_empty_response: dict,
        mock_linked: AsyncMock,
        mock_linear_settings: dict,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_empty_response

            task = await get_linear_task("demetra")

        assert task is None

    @pytest.mark.asyncio
    async def test_update_ticket_status_returns_true_on_success(
        self,
        graphql_update_success_response: dict,
    ):
        with (
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_request.return_value = graphql_update_success_response
            result = await update_ticket_status("issue-1", "state-1")

        assert result is True

    @pytest.mark.asyncio
    async def test_update_ticket_status_returns_false_on_failure(
        self,
        graphql_update_failure_response: dict,
    ):
        with (
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_request.return_value = graphql_update_failure_response
            result = await update_ticket_status("issue-1", "state-1")

        assert result is False

    @pytest.mark.asyncio
    async def test_post_comment_returns_true_on_success(
        self,
        graphql_comment_success_response: dict,
    ):
        with (
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_request.return_value = graphql_comment_success_response
            result = await post_comment("issue-1", "Test comment")

        assert result is True

    @pytest.mark.asyncio
    async def test_post_comment_returns_false_on_failure(
        self,
        graphql_comment_failure_response: dict,
    ):
        with (
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_request.return_value = graphql_comment_failure_response
            result = await post_comment("issue-1", "Test comment")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_todo_issues_includes_comments(
        self,
        graphql_todo_issues_response_with_comments: dict,
        mock_linked: AsyncMock,
        mock_linear_settings: dict,
    ):
        mock_linear_settings["comments"] = {}

        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_todo_issues_response_with_comments

            issues = await get_todo_issues("demetra")

        assert len(issues) == 1
        assert len(issues[0].comments) == 3
        assert issues[0].comments[0] == "First question from the team?"
        assert issues[0].comments[1] == "Answer to first question"
        assert issues[0].comments[2] == "Second question about the implementation?"

    @pytest.mark.asyncio
    async def test_get_todo_issues_empty_comments(
        self,
        graphql_todo_issues_response_demetra: dict,
        mock_linked: AsyncMock,
        mock_linear_settings: dict,
    ):
        mock_linear_settings["comments"] = {}

        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_todo_issues_response_demetra

            issues = await get_todo_issues("demetra")

        assert len(issues) == 1
        assert issues[0].comments == []

    @pytest.mark.asyncio
    async def test_linear_task_text_includes_comments(
        self,
        graphql_todo_issues_response_with_comments: dict,
        mock_linked: AsyncMock,
        mock_linear_settings: dict,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_todo_issues_response_with_comments

            issues = await get_todo_issues("demetra")

        task_text = issues[0].text
        assert "Comments:" in task_text
        assert "First question" in task_text
        assert "Second question" in task_text

    @pytest.mark.asyncio
    async def test_get_todo_issues_enriches_with_project_id_and_user_id(
        self,
        graphql_todo_issues_response_demetra: dict,
        mock_linked_projects: dict,
        mock_linked: AsyncMock,
        mock_linear_settings: dict,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_todo_issues_response_demetra

            issues = await get_todo_issues()

        assert len(issues) == 1
        project_id, user_id = mock_linked_projects["demetra"]
        assert issues[0].project_id == project_id
        assert issues[0].user_id == user_id

    @pytest.mark.asyncio
    async def test_get_todo_issues_includes_labels(
        self,
        graphql_todo_issues_response_with_labels: dict,
        mock_linked: AsyncMock,
        mock_linear_settings: dict,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_todo_issues_response_with_labels

            issues = await get_todo_issues("demetra")

        assert len(issues) == 1
        assert issues[0].labels == ["bug", "frontend"]

    @pytest.mark.asyncio
    async def test_get_todo_issues_empty_labels(
        self,
        graphql_todo_issues_response_demetra: dict,
        mock_linked: AsyncMock,
        mock_linear_settings: dict,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_todo_issues_response_demetra

            issues = await get_todo_issues("demetra")

        assert len(issues) == 1
        assert issues[0].labels == []

    @pytest.mark.asyncio
    async def test_get_todo_issues_filter_labels_includes_matching(
        self,
        graphql_todo_issues_response_with_labels: dict,
        mock_linked: AsyncMock,
        mock_linear_settings: dict,
    ):
        mock_linear_settings["filter_labels"] = ["bug"]

        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_todo_issues_response_with_labels

            issues = await get_todo_issues("demetra")

        assert len(issues) == 1
        assert "bug" in issues[0].labels

    @pytest.mark.asyncio
    async def test_get_todo_issues_filter_labels_skips_non_matching(
        self,
        graphql_todo_issues_response_with_labels: dict,
        mock_linked: AsyncMock,
        mock_linear_settings: dict,
    ):
        mock_linear_settings["filter_labels"] = ["backend"]

        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_todo_issues_response_with_labels

            issues = await get_todo_issues("demetra")

        assert issues == []

    @pytest.mark.asyncio
    async def test_get_todo_issues_filter_labels_empty_allows_all(
        self,
        graphql_todo_issues_response_with_labels: dict,
        mock_linked: AsyncMock,
        mock_linear_settings: dict,
    ):
        mock_linear_settings["filter_labels"] = []

        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_todo_issues_response_with_labels

            issues = await get_todo_issues("demetra")

        assert len(issues) == 1

    @pytest.mark.asyncio
    async def test_get_todo_issues_filter_labels_case_insensitive(
        self,
        graphql_todo_issues_response_with_labels: dict,
        mock_linked: AsyncMock,
        mock_linear_settings: dict,
    ):
        mock_linear_settings["filter_labels"] = ["FRONTEND"]

        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_todo_issues_response_with_labels

            issues = await get_todo_issues("demetra")

        assert len(issues) == 1


class TestExtractComments:
    def test_extract_unresolved_comments_with_children(self):
        issue = {
            "comments": {
                "nodes": [
                    {
                        "body": "Parent question",
                        "resolvedAt": None,
                        "children": {
                            "edges": [
                                {"node": {"body": "Reply answer"}},
                            ]
                        },
                    }
                ]
            }
        }
        result = extract_comments(issue)
        assert result == ["Parent question", "Reply answer"]

    def test_extract_skips_resolved_comments(self):
        issue = {
            "comments": {
                "nodes": [
                    {"body": "Resolved question", "resolvedAt": "2026-01-01T00:00:00Z", "children": {"edges": []}},
                    {"body": "Unresolved question", "resolvedAt": None, "children": {"edges": []}},
                ]
            }
        }
        result = extract_comments(issue)
        assert result == ["Unresolved question"]

    def test_extract_empty_comments(self):
        issue = {"comments": {"nodes": []}}
        result = extract_comments(issue)
        assert result == []

    def test_extract_missing_comments_key(self):
        result = extract_comments({})
        assert result == []

    def test_extract_handles_missing_body(self):
        issue = {
            "comments": {
                "nodes": [
                    {"body": None, "resolvedAt": None, "children": {"edges": []}},
                ]
            }
        }
        result = extract_comments(issue)
        assert result == [None]

    def test_extract_handles_missing_child_body(self):
        issue = {
            "comments": {
                "nodes": [
                    {
                        "body": "Parent",
                        "resolvedAt": None,
                        "children": {"edges": [{"node": {"body": None}}]},
                    }
                ]
            }
        }
        result = extract_comments(issue)
        assert result == ["Parent"]


class TestExtractLabels:
    def test_extract_labels_returns_names(self):
        issue = {
            "labels": {
                "nodes": [
                    {"id": "l1", "name": "bug"},
                    {"id": "l2", "name": "frontend"},
                ]
            }
        }
        assert extract_labels(issue) == ["bug", "frontend"]

    def test_extract_labels_skips_missing_name(self):
        issue = {
            "labels": {
                "nodes": [
                    {"id": "l1", "name": "bug"},
                    {"id": "l2", "name": None},
                    {"id": "l3"},
                ]
            }
        }
        assert extract_labels(issue) == ["bug"]

    def test_extract_labels_empty(self):
        assert extract_labels({"labels": {"nodes": []}}) == []

    def test_extract_labels_missing_key(self):
        assert extract_labels({}) == []


class TestGetLinkedProjects:
    @pytest_asyncio.fixture(autouse=True)
    async def _clean_projects(self, setup_test_db):
        yield
        async with _get_connection() as conn:
            await conn.execute(project_environments.delete())
            await conn.execute(projects.delete())
            await conn.commit()

    @pytest.mark.asyncio
    async def test_get_linked_projects_returns_mapping(self, faker, setup_test_db):
        proj_a = await create_project(
            user_id="user-1",
            name="project-alpha",
            repository_url="https://github.com/owner/alpha",
            repository_owner="owner",
            repository_name="alpha",
            linear_project_id="linear-proj-aaa",
        )
        proj_b = await create_project(
            user_id="user-2",
            name="project-beta",
            repository_url="https://github.com/owner/beta",
            repository_owner="owner",
            repository_name="beta",
            linear_project_id="linear-proj-bbb",
        )

        result = await get_linked_projects()

        assert result["linear-proj-aaa"] == (proj_a["id"], "user-1")
        assert result["project-alpha"] == (proj_a["id"], "user-1")
        assert result["linear-proj-bbb"] == (proj_b["id"], "user-2")
        assert result["project-beta"] == (proj_b["id"], "user-2")

    @pytest.mark.asyncio
    async def test_get_linked_projects_skips_projects_without_linear_id(self, faker, setup_test_db):
        await create_project(
            user_id="user-1",
            name="no-linear-project",
            repository_url="https://github.com/owner/no-linear",
            repository_owner="owner",
            repository_name="no-linear",
            linear_project_id=None,
        )

        result = await get_linked_projects()
        assert result["no-linear-project"] is not None


class TestCreateLinearTicket:
    @pytest.fixture
    def mock_get_query(self):
        with patch("demetra.services.linear.get_query", new_callable=AsyncMock) as m:
            yield m

    @pytest.mark.asyncio
    async def test_create_ticket_returns_ticket_data(
        self,
        graphql_create_ticket_success_response: dict,
        linear_issue_id: str,
        linear_identifier: str,
        mock_get_query: AsyncMock,
    ):
        mock_get_query.return_value = "mutation IssueCreate..."

        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_create_ticket_success_response

            result = await create_linear_ticket(
                title="Test ticket",
                description="Test description",
                technical_requirements="Tech reqs",
                acceptance_criteria="AC",
            )

        assert result["ticket_id"] == linear_issue_id
        assert result["identifier"] == linear_identifier
        assert result["title"] == "Test ticket"

    @pytest.mark.asyncio
    async def test_create_ticket_raises_on_failure(
        self,
        graphql_create_ticket_failure_response: dict,
        mock_get_query: AsyncMock,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_create_ticket_failure_response

            with pytest.raises(LinearError, match="Failed to create Linear ticket"):
                await create_linear_ticket(
                    title="Test",
                    description="Test",
                    technical_requirements="Test",
                    acceptance_criteria="Test",
                )

    @pytest.mark.asyncio
    async def test_create_ticket_raises_when_no_issue_data(
        self,
        graphql_create_ticket_no_issue_response: dict,
        mock_get_query: AsyncMock,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_create_ticket_no_issue_response

            with pytest.raises(LinearError, match="success but no issue data"):
                await create_linear_ticket(
                    title="Test",
                    description="Test",
                    technical_requirements="Test",
                    acceptance_criteria="Test",
                )

    @pytest.mark.asyncio
    async def test_create_ticket_builds_full_description(
        self,
        graphql_create_ticket_success_response: dict,
        mock_get_query: AsyncMock,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_create_ticket_success_response

            await create_linear_ticket(
                title="Test",
                description="The description",
                technical_requirements="Tech",
                acceptance_criteria="AC",
            )

        _, kwargs = mock_request.call_args
        variables = kwargs["variables"]
        desc = variables["input"]["description"]
        assert "### Description" in desc
        assert "The description" in desc
        assert "### Tech Requirements" in desc
        assert "Tech" in desc
        assert "### Acceptance Criteria" in desc
        assert "AC" in desc


class TestGetLinearTaskById:
    @pytest.fixture
    def mock_linked(self, mock_linked_projects):
        with patch("demetra.services.linear.get_linked_projects", new_callable=AsyncMock) as m:
            m.return_value = mock_linked_projects
            yield m

    @pytest.mark.asyncio
    async def test_get_linear_task_by_id_returns_task(
        self,
        graphql_get_issue_by_id_response: dict,
        mock_linked: AsyncMock,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_get_issue_by_id_response

            task = await get_linear_task_by_id("issue-1")

        assert task is not None
        assert task.id is not None
        assert task.identifier is not None
        assert task.title is not None

    @pytest.mark.asyncio
    async def test_get_linear_task_by_id_returns_none_when_not_found(
        self,
        graphql_get_issue_by_id_not_found_response: dict,
        mock_linked: AsyncMock,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_get_issue_by_id_not_found_response

            task = await get_linear_task_by_id("invalid-id")

        assert task is None

    @pytest.mark.asyncio
    async def test_get_linear_task_by_id_extracts_comments(
        self,
        graphql_get_issue_by_id_response_with_comments: dict,
        mock_linked: AsyncMock,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_get_issue_by_id_response_with_comments

            task = await get_linear_task_by_id("issue-1")

        assert task is not None
        assert len(task.comments) > 0
        assert "First question" in task.comments[0]
        assert "Answer to first question" in task.comments[1]

    @pytest.mark.asyncio
    async def test_get_linear_task_by_id_enriches_with_project_id(
        self,
        graphql_get_issue_by_id_response: dict,
        mock_linked_projects: dict,
        mock_linked: AsyncMock,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_get_issue_by_id_response

            task = await get_linear_task_by_id("issue-1")

        assert task is not None
        project_id, user_id = mock_linked_projects["demetra"]
        assert task.project_id == project_id
        assert task.user_id == user_id

    @pytest.mark.asyncio
    async def test_get_linear_task_by_id_includes_labels(
        self,
        graphql_get_issue_by_id_response_with_labels: dict,
        mock_linked: AsyncMock,
    ):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = graphql_get_issue_by_id_response_with_labels

            task = await get_linear_task_by_id("issue-1")

        assert task is not None
        assert task.labels == ["bug", "frontend"]


class TestLinearCleanup:
    @pytest.fixture
    def mock_linear_settings(self, linear_full_settings):
        with patch("demetra.services.linear.LINEAR", linear_full_settings):
            yield linear_full_settings

    @pytest.fixture
    def mock_print_message(self):
        with patch("demetra.services.linear.print_message"):
            yield

    @pytest.mark.asyncio
    async def test_cleanup_success_moves_to_in_review(
        self,
        faker,
        mock_linear_settings: dict,
        mock_print_message,
    ):
        context = Context(
            project=Project(
                id=str(uuid4()),
                user_id=str(uuid4()),
                linear_project_id=str(uuid4()),
                name="demetra",
                state="active",
                repository_url="https://github.com/test/demetra",
                repository_name="demetra",
                repository_owner="test",
                local_path=Path(f"/tmp/{faker.slug()}"),
                created_at="2026-01-01T00:00:00",
                updated_at="2026-01-01T00:00:00",
            ),
            auto_mode=False,
            linear_task=LinearTask(
                id="linear-task-123",
                identifier="MNT-123",
                title=faker.sentence(),
                description=faker.text(),
                priority=1,
                created_at="2026-01-01T00:00:00",
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        with patch("demetra.services.linear.update_ticket_status", new_callable=AsyncMock) as mock_update:
            await linear_cleanup(context, is_success=True)

        mock_update.assert_awaited_once_with(
            task_id="linear-task-123",
            state_id=mock_linear_settings["states"]["in_review"],
        )

    @pytest.mark.asyncio
    async def test_cleanup_failure_moves_to_todo(
        self,
        faker,
        mock_linear_settings: dict,
        mock_print_message,
    ):
        context = Context(
            project=Project(
                id=str(uuid4()),
                user_id=str(uuid4()),
                linear_project_id=str(uuid4()),
                name="demetra",
                state="active",
                repository_url="https://github.com/test/demetra",
                repository_name="demetra",
                repository_owner="test",
                local_path=Path(f"/tmp/{faker.slug()}"),
                created_at="2026-01-01T00:00:00",
                updated_at="2026-01-01T00:00:00",
            ),
            auto_mode=False,
            linear_task=LinearTask(
                id="linear-task-456",
                identifier="MNT-456",
                title=faker.sentence(),
                description=faker.text(),
                priority=1,
                created_at="2026-01-01T00:00:00",
            ),
            branch_name="feature/test",
            worktree_path=Path(f"/tmp/{faker.slug()}"),
            session=None,
        )

        with patch("demetra.services.linear.update_ticket_status", new_callable=AsyncMock) as mock_update:
            await linear_cleanup(context, is_success=False)

        mock_update.assert_awaited_once_with(
            task_id="linear-task-456",
            state_id=mock_linear_settings["states"]["todo"],
        )
