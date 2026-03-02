import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


class TestProcessManager:
    @pytest.fixture(autouse=True)
    async def setup(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = Path(self.temp_db.name)
        self.patcher = patch("demetra.services.database.DB_PATH", self.db_path)
        self.patcher.start()
        from demetra.services import database

        await database.init_db()
        yield
        self.patcher.stop()
        self.db_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_add_pending_task(self):
        from demetra.services.database import add_pending_task, get_task_status

        await add_pending_task("task-123", "demetra")
        status = await get_task_status("task-123")
        assert status == "pending"

    @pytest.mark.asyncio
    async def test_mark_task_processed(self):
        from demetra.services.database import add_pending_task, get_task_status, mark_task_processed

        await add_pending_task("task-456", "demetra")
        await mark_task_processed("task-456")
        status = await get_task_status("task-456")
        assert status == "processed"

    @pytest.mark.asyncio
    async def test_mark_task_failed(self):
        from demetra.services.database import add_pending_task, get_task_status, mark_task_failed

        await add_pending_task("task-789", "demetra")
        await mark_task_failed("task-789")
        status = await get_task_status("task-789")
        assert status == "failed"

    @pytest.mark.asyncio
    async def test_get_pending_task_ids(self):
        from demetra.services.database import add_pending_task, get_pending_task_ids, mark_task_processed

        await add_pending_task("task-1", "demetra")
        await add_pending_task("task-2", "chimera")
        await add_pending_task("task-3", "odin")
        await mark_task_processed("task-2")

        pending = await get_pending_task_ids()
        assert pending == {"task-1", "task-3"}

    @pytest.mark.asyncio
    async def test_get_all_todo_issues_returns_all_projects(
        self,
        graphql_todo_issues_multiple_response: dict,
    ):
        from demetra.models import LinearTask
        from demetra.services.linear import get_todo_issues

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = graphql_todo_issues_multiple_response
            with patch("demetra.services.linear.LINEAR_TEAM_ID", "team-123"):
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
        mock_data["data"]["team"]["states"]["nodes"][0]["issues"]["nodes"][0]["project"] = None

        with (
            patch("demetra.services.linear.get_query", new_callable=AsyncMock) as mock_query,
            patch("demetra.services.linear.graphql_request", new_callable=AsyncMock) as mock_request,
        ):
            mock_query.return_value = "query"
            mock_request.return_value = mock_data
            with patch("demetra.services.linear.LINEAR_TEAM_ID", "team-123"):
                issues = await get_todo_issues()

        assert len(issues) == 2
        assert issues[0].project_name is None
