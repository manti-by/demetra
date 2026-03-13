from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest


class TestProcessManager:
    @pytest.mark.asyncio
    async def test_add_pending_task(self):
        from demetra.services.database import add_pending_task, get_task_status

        task_id = f"task-add-{uuid4().hex[:8]}"
        await add_pending_task(task_id, "demetra")
        status = await get_task_status(task_id)
        assert status == "pending"

    @pytest.mark.asyncio
    async def test_mark_task_processed(self):
        from demetra.services.database import add_pending_task, get_task_status, mark_task_processed

        task_id = f"task-process-{uuid4().hex[:8]}"
        await add_pending_task(task_id, "demetra")
        await mark_task_processed(task_id)
        status = await get_task_status(task_id)
        assert status == "processed"

    @pytest.mark.asyncio
    async def test_mark_task_failed(self):
        from demetra.services.database import add_pending_task, get_task_status, mark_task_failed

        task_id = f"task-fail-{uuid4().hex[:8]}"
        await add_pending_task(task_id, "demetra")
        await mark_task_failed(task_id)
        status = await get_task_status(task_id)
        assert status == "failed"

    @pytest.mark.asyncio
    async def test_get_pending_task_ids(self):
        from demetra.services.database import add_pending_task, get_pending_task_ids, mark_task_processed

        task_1 = f"task-1-{uuid4().hex[:8]}"
        task_2 = f"task-2-{uuid4().hex[:8]}"
        task_3 = f"task-3-{uuid4().hex[:8]}"
        await add_pending_task(task_1, "demetra")
        await add_pending_task(task_2, "chimera")
        await add_pending_task(task_3, "odin")
        await mark_task_processed(task_2)

        pending = await get_pending_task_ids()
        assert task_1 in pending
        assert task_3 in pending
        assert task_2 not in pending

    @pytest.mark.asyncio
    async def test_get_all_todo_issues_returns_all_projects(
        self,
        graphql_todo_issues_multiple_response: dict,
    ):
        from demetra.library.models import LinearTask
        from demetra.services.linear import get_todo_issues

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = graphql_todo_issues_multiple_response
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

        assert len(issues) == 2
        assert isinstance(issues[0], LinearTask)

    @pytest.mark.asyncio
    async def test_get_all_todo_issues_filters_out_issues_without_project(
        self,
        graphql_todo_issues_multiple_response: dict,
    ):
        from demetra.services.linear import get_todo_issues

        mock_data = graphql_todo_issues_multiple_response.copy()
        mock_data["data"]["issues"]["nodes"][0]["project"] = None

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = mock_data
            with patch(
                "demetra.services.linear.LINEAR",
                {
                    "team_id": "team-123",
                    "default_state": "s1",
                    "default_project": "p1",
                    "feature_label_id": "l1",
                    "states": {},
                    "projects": {},
                    "comments": {},
                },
            ):
                issues = await get_todo_issues()

        assert len(issues) == 2
        assert issues[0].project_name is None
