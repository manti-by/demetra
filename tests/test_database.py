import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestDatabaseService:
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
    async def test_create_and_read(self):
        from demetra.services.database import create_session, get_session

        record = await create_session("TICKET-1", "session-123")
        assert record.task_id == "TICKET-1"
        assert record.session_id == "session-123"
        assert record.build_plan == ""
        assert record.posted_to_linear is False

        found = await get_session("TICKET-1")
        assert found is not None
        assert found.task_id == "TICKET-1"
        assert found.session_id == "session-123"

    @pytest.mark.asyncio
    async def test_read_nonexistent(self):
        from demetra.services.database import get_session

        result = await get_session("TICKET-999")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_session_with_build_plan(self):
        from demetra.services.database import get_session, save_session

        session = await save_session("TASK-1", "session-123", "Step 1: Do this\nStep 2: Do that")
        assert session.task_id == "TASK-1"
        assert session.session_id == "session-123"
        assert session.build_plan == "Step 1: Do this\nStep 2: Do that"
        assert session.posted_to_linear is False

        found = await get_session("TASK-1")
        assert found is not None
        assert found.task_id == "TASK-1"
        assert found.build_plan == "Step 1: Do this\nStep 2: Do that"
        assert found.posted_to_linear is False

    @pytest.mark.asyncio
    async def test_save_session_updates_existing(self):
        from demetra.services.database import get_session, save_session

        await save_session("TASK-2", "session-1", "Original plan")
        await save_session("TASK-2", "session-2", "Updated plan")

        found = await get_session("TASK-2")
        assert found is not None
        assert found.session_id == "session-2"
        assert found.build_plan == "Updated plan"
        assert found.posted_to_linear is False

    @pytest.mark.asyncio
    async def test_save_session_preserves_posted_to_linear(self):
        from demetra.services.database import get_session, mark_session_posted, save_session

        await save_session("TASK-3", "session-1", "Plan A")
        await mark_session_posted("TASK-3")

        await save_session("TASK-3", "session-2", "Plan B")
        found = await get_session("TASK-3")
        assert found is not None
        assert found.build_plan == "Plan B"
        assert found.posted_to_linear is True

    @pytest.mark.asyncio
    async def test_mark_session_posted(self):
        from demetra.services.database import get_session, mark_session_posted, save_session

        await save_session("TASK-4", "session-1", "My build plan")
        found = await get_session("TASK-4")
        assert found is not None
        assert found.posted_to_linear is False

        await mark_session_posted("TASK-4")
        found = await get_session("TASK-4")
        assert found is not None
        assert found.posted_to_linear is True
