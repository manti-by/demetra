from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from demetra.services.linear import get_todo_issues
from demetra.services.persistence.database import (
    get_pending_session_task_ids,
    get_session,
    upsert_pending_session,
)


class TestProcessManager:
    @pytest.fixture
    def mock_graphql_request(self):
        with patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture
    def mock_get_linked_projects(self):
        with patch("demetra.services.linear.get_linked_projects", new_callable=AsyncMock) as mock:
            yield mock

    @pytest.fixture(autouse=True)
    def mock_linear_settings(self):
        with patch(
            "demetra.services.linear.LINEAR",
            {
                "team_id": "team-123",
                "default_state": "s1",
                "default_project": "p1",
                "feature_label_id": "l1",
                "states": {"todo": "state-todo"},
                "projects": {},
            },
        ):
            yield

    @pytest.mark.asyncio
    async def test_get_todo_issues_returns_only_linked_projects(
        self,
        graphql_todo_issues_response_demetra: dict,
        mock_graphql_request,
        mock_get_linked_projects,
    ):
        project_id = str(uuid4())
        user_id = str(uuid4())
        mock_linked_projects = {project_id: (project_id, user_id), "demetra": (project_id, user_id)}

        mock_graphql_request.return_value = graphql_todo_issues_response_demetra
        mock_get_linked_projects.return_value = mock_linked_projects

        issues = await get_todo_issues()

        assert len(issues) == 1
        assert issues[0].project_name == "demetra"
        assert issues[0].project_id == project_id
        assert issues[0].user_id == user_id

    @pytest.mark.asyncio
    async def test_get_todo_issues_non_linked_returns_none_project_id(
        self,
        graphql_todo_issues_response_demetra: dict,
        mock_graphql_request,
        mock_get_linked_projects,
    ):
        mock_linked_projects = {}

        mock_graphql_request.return_value = graphql_todo_issues_response_demetra
        mock_get_linked_projects.return_value = mock_linked_projects

        issues = await get_todo_issues("demetra")

        assert len(issues) == 1
        assert issues[0].project_id is None
        assert issues[0].user_id is None

    @pytest.mark.asyncio
    async def test_pending_session_workflow(self, setup_test_db):
        task_id = f"session-step-{uuid4().hex[:8]}"
        project_id = str(uuid4())
        user_id = str(uuid4())

        await upsert_pending_session(
            task_id=task_id,
            session_id=None,
            project_id=project_id,
            user_id=user_id,
        )

        session = await get_session(task_id)
        assert session is not None
        assert session.step == "initial"
        assert session.project_id == project_id
        assert session.user_id == user_id

        pending = await get_pending_session_task_ids()
        assert task_id in pending
