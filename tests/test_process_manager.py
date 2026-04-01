from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest


class TestProcessManager:
    @pytest.mark.asyncio
    async def test_get_todo_issues_returns_only_linked_projects(
        self,
        graphql_todo_issues_response_demetra: dict,
    ):
        from demetra.services.linear import get_todo_issues

        project_id = str(uuid4())
        user_id = str(uuid4())
        mock_linked_projects = {project_id: (project_id, user_id), "demetra": (project_id, user_id)}

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
            patch("demetra.services.linear._get_linked_projects", new_callable=AsyncMock) as mock_linked,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = graphql_todo_issues_response_demetra
            mock_linked.return_value = mock_linked_projects

            with patch(
                "demetra.services.linear.LINEAR",
                {
                    "team_id": "team-123",
                    "default_state": "s1",
                    "default_project": "p1",
                    "feature_label_id": "l1",
                    "states": {},
                    "projects": {},
                },
            ):
                issues = await get_todo_issues()

        assert len(issues) == 1
        assert issues[0].project_name == "demetra"
        assert issues[0].project_id == project_id
        assert issues[0].user_id == user_id

    @pytest.mark.asyncio
    async def test_get_todo_issues_non_linked_returns_none_project_id(
        self,
        graphql_todo_issues_response_demetra: dict,
    ):
        from demetra.services.linear import get_todo_issues

        mock_linked_projects = {}

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
            patch("demetra.services.linear._get_linked_projects", new_callable=AsyncMock) as mock_linked,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = graphql_todo_issues_response_demetra
            mock_linked.return_value = mock_linked_projects

            with patch(
                "demetra.services.linear.LINEAR",
                {
                    "team_id": "team-123",
                    "default_state": "s1",
                    "default_project": "p1",
                    "feature_label_id": "l1",
                    "states": {},
                    "projects": {},
                },
            ):
                issues = await get_todo_issues("demetra")

        assert len(issues) == 1
        assert issues[0].project_id is None
        assert issues[0].user_id is None

    @pytest.mark.asyncio
    async def test_session_status_workflow(self, setup_test_db):
        from demetra.services.database import (
            get_pending_session_task_ids,
            get_session,
            update_session_status,
            upsert_pending_session,
        )

        task_id = f"session-status-{uuid4().hex[:8]}"
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
        assert session.status == "pending"
        assert session.project_id == project_id
        assert session.user_id == user_id

        pending = await get_pending_session_task_ids()
        assert task_id in pending

        await update_session_status(task_id=task_id, status="processed")
        session = await get_session(task_id)
        assert session is not None
        assert session.status == "processed"

        await update_session_status(task_id=task_id, status="failed")
        session = await get_session(task_id)
        assert session is not None
        assert session.status == "failed"
