from unittest.mock import AsyncMock, patch

import pytest


class TestDatabaseService:
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
    async def test_create_and_read(
        self,
        db_task_id: str,
        db_session_id: str,
    ):
        from demetra.services.database import create_session, get_session

        self._reset_mocks()

        record = await create_session(db_task_id, db_session_id)
        assert record.task_id == db_task_id
        assert record.session_id == db_session_id
        assert record.build_plan == ""
        assert record.posted_to_linear is False

        self.mock_cursor.fetchone = AsyncMock(
            return_value={
                "task_id": db_task_id,
                "session_id": db_session_id,
                "build_plan": "",
                "posted_to_linear": False,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            }
        )
        found = await get_session(db_task_id)
        assert found is not None
        assert found.task_id == db_task_id
        assert found.session_id == db_session_id

    @pytest.mark.asyncio
    async def test_read_nonexistent(self):
        from demetra.services.database import get_session

        self._reset_mocks()

        result = await get_session("TICKET-999")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_session_with_build_plan(
        self,
        db_task_id: str,
        db_session_id: str,
        db_build_plan: str,
    ):
        from demetra.services.database import get_session, save_session

        self._reset_mocks()

        session = await save_session(db_task_id, db_session_id, db_build_plan)
        assert session.task_id == db_task_id
        assert session.session_id == db_session_id
        assert session.build_plan == db_build_plan
        assert session.posted_to_linear is False

        self.mock_cursor.fetchone = AsyncMock(
            return_value={
                "task_id": db_task_id,
                "session_id": db_session_id,
                "build_plan": db_build_plan,
                "posted_to_linear": False,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
            }
        )
        found = await get_session(db_task_id)
        assert found is not None
        assert found.task_id == db_task_id
        assert found.build_plan == db_build_plan
        assert found.posted_to_linear is False

    @pytest.mark.asyncio
    async def test_save_session_updates_existing(
        self,
        db_task_id: str,
        db_session_id: str,
    ):
        from demetra.services.database import get_session, save_session

        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_cursor = AsyncMock()
            mock_cursor.fetchone = AsyncMock(return_value=None)
            return mock_cursor

        self.mock_conn.execute = AsyncMock(side_effect=execute_side_effect)

        await save_session(db_task_id, db_session_id, "Original plan")
        call_count[0] = 0
        await save_session(db_task_id, f"session-{db_session_id}", "Updated plan")

        self.mock_cursor.fetchone = AsyncMock(
            return_value={
                "task_id": db_task_id,
                "session_id": f"session-{db_session_id}",
                "build_plan": "Updated plan",
                "posted_to_linear": False,
                "created_at": "2024-01-01",
                "updated_at": "2024-01-02",
            }
        )
        self.mock_conn.execute = AsyncMock(return_value=self.mock_cursor)
        found = await get_session(db_task_id)
        assert found is not None
        assert found.session_id != db_session_id
        assert found.build_plan == "Updated plan"
        assert found.posted_to_linear is False

    @pytest.mark.asyncio
    async def test_save_session_preserves_posted_to_linear(
        self,
        db_task_id: str,
        db_session_id: str,
    ):
        from demetra.services.database import get_session, mark_session_posted, save_session

        class MockRow(dict):
            def __getattr__(self, key):
                return self.get(key)

        fetch_results = [
            None,
            None,
            MockRow({"posted_to_linear": True, "created_at": "2024-01-01"}),
            None,
            None,
            MockRow(
                {
                    "task_id": db_task_id,
                    "session_id": f"session-{db_session_id}",
                    "build_plan": "Plan B",
                    "posted_to_linear": True,
                    "created_at": "2024-01-01",
                    "updated_at": "2024-01-02",
                }
            ),
        ]
        fetch_index = [0]

        async def mock_execute(*args, **kwargs):
            mock_cursor = AsyncMock()
            idx = fetch_index[0]
            fetch_index[0] += 1
            if idx < len(fetch_results):
                mock_cursor.fetchone = AsyncMock(return_value=fetch_results[idx])
            else:
                mock_cursor.fetchone = AsyncMock(return_value=None)
            return mock_cursor

        self.mock_conn.execute = mock_execute

        await save_session(db_task_id, db_session_id, "Plan A")
        await mark_session_posted(db_task_id)
        await save_session(db_task_id, f"session-{db_session_id}", "Plan B")

        self.mock_cursor.fetchone = AsyncMock(
            return_value=MockRow(
                {
                    "task_id": db_task_id,
                    "session_id": f"session-{db_session_id}",
                    "build_plan": "Plan B",
                    "posted_to_linear": True,
                    "created_at": "2024-01-01",
                    "updated_at": "2024-01-02",
                }
            )
        )
        self.mock_conn.execute = AsyncMock(return_value=self.mock_cursor)
        found = await get_session(db_task_id)
        assert found is not None
        assert found.build_plan == "Plan B"
        assert found.posted_to_linear is True

    @pytest.mark.asyncio
    async def test_mark_session_posted(
        self,
        db_task_id: str,
        db_session_id: str,
    ):
        from demetra.services.database import get_session, mark_session_posted, save_session

        self._reset_mocks()

        await save_session(db_task_id, db_session_id, "My build plan")

        self.mock_cursor.fetchone = AsyncMock(
            return_value={
                "task_id": db_task_id,
                "session_id": db_session_id,
                "build_plan": "My build plan",
                "posted_to_linear": False,
                "created_at": "2024-01-01",
                "updated_at": "2024-01-01",
            }
        )
        found = await get_session(db_task_id)
        assert found is not None
        assert found.posted_to_linear is False

        self.mock_cursor.fetchone = AsyncMock(
            return_value={
                "task_id": db_task_id,
                "session_id": db_session_id,
                "build_plan": "My build plan",
                "posted_to_linear": True,
                "created_at": "2024-01-01",
                "updated_at": "2024-01-02",
            }
        )
        await mark_session_posted(db_task_id)
        found = await get_session(db_task_id)
        assert found is not None
        assert found.posted_to_linear is True
