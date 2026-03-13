from unittest.mock import AsyncMock, patch

import pytest


class TestProcessManager:
    @pytest.fixture(autouse=True)
    def setup(self):
        import demetra.services.database as database

        self.mock_conn = AsyncMock()
        self.mock_cursor = AsyncMock()
        self.mock_conn.execute = AsyncMock()
        self.mock_conn.commit = AsyncMock()
        self.mock_conn.close = AsyncMock()
        self.mock_conn.__aenter__ = AsyncMock(return_value=self.mock_conn)
        self.mock_conn.__aexit__ = AsyncMock(return_value=None)

        self.patcher = patch.object(database, "get_connection")
        self.mock_get_conn = self.patcher.start()
        self.mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=self.mock_conn)
        self.mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
        yield
        self.patcher.stop()

    def _reset_mocks(self):
        self.mock_cursor.fetchone = AsyncMock(return_value=None)
        self.mock_conn.execute = AsyncMock(return_value=self.mock_cursor)

    @pytest.mark.asyncio
    async def test_add_pending_task(self):
        from demetra.services.database import add_pending_task, get_task_status

        self._reset_mocks()

        await add_pending_task("task-123", "demetra")
        self.mock_cursor.fetchone = AsyncMock(return_value={"status": "pending"})
        status = await get_task_status("task-123")
        assert status == "pending"

    @pytest.mark.asyncio
    async def test_mark_task_processed(self):
        from demetra.services.database import add_pending_task, get_task_status, mark_task_processed

        self._reset_mocks()

        await add_pending_task("task-456", "demetra")
        await mark_task_processed("task-456")
        self.mock_cursor.fetchone = AsyncMock(return_value={"status": "processed"})
        status = await get_task_status("task-456")
        assert status == "processed"

    @pytest.mark.asyncio
    async def test_mark_task_failed(self):
        from demetra.services.database import add_pending_task, get_task_status, mark_task_failed

        self._reset_mocks()

        await add_pending_task("task-789", "demetra")
        await mark_task_failed("task-789")
        self.mock_cursor.fetchone = AsyncMock(return_value={"status": "failed"})
        status = await get_task_status("task-789")
        assert status == "failed"

    @pytest.mark.asyncio
    async def test_get_pending_task_ids(self):
        from demetra.services.database import add_pending_task, get_pending_task_ids, mark_task_processed

        class MockRow(dict):
            def __getattr__(self, key):
                return self.get(key)

        def create_mock_cursor(result):
            mock_cursor = AsyncMock()
            mock_cursor.fetchone = AsyncMock(return_value=result if isinstance(result, dict) else None)
            mock_cursor.fetchall = AsyncMock(return_value=result if isinstance(result, list) else [])
            return mock_cursor

        call_results = [
            create_mock_cursor(None),
            create_mock_cursor(None),
            create_mock_cursor(None),
            create_mock_cursor(None),
            create_mock_cursor(None),
            create_mock_cursor(None),
            create_mock_cursor(None),
            create_mock_cursor([MockRow({"task_id": "task-1"}), MockRow({"task_id": "task-3"})]),
        ]
        call_index = [0]

        async def mock_execute(*args, **kwargs):
            idx = call_index[0]
            call_index[0] += 1
            if idx < len(call_results):
                return call_results[idx]
            return create_mock_cursor(None)

        self.mock_conn.execute = mock_execute

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
