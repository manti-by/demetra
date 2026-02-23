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

        found = await get_session("TICKET-1")
        assert found is not None

    @pytest.mark.asyncio
    async def test_read_nonexistent(self):
        from demetra.services.database import get_session

        result = await get_session("TICKET-999")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_and_get_build_plan(self):
        from demetra.services.database import get_build_plan, save_build_plan

        plan = await save_build_plan("TASK-1", "Step 1: Do this\nStep 2: Do that")
        assert plan.task_id == "TASK-1"
        assert plan.plan_content == "Step 1: Do this\nStep 2: Do that"
        assert plan.posted_to_linear is False

        found = await get_build_plan("TASK-1")
        assert found is not None
        assert found.task_id == "TASK-1"
        assert found.plan_content == "Step 1: Do this\nStep 2: Do that"
        assert found.posted_to_linear is False

    @pytest.mark.asyncio
    async def test_get_nonexistent_build_plan(self):
        from demetra.services.database import get_build_plan

        result = await get_build_plan("TASK-999")
        assert result is None

    @pytest.mark.asyncio
    async def test_mark_build_plan_posted(self):
        from demetra.services.database import get_build_plan, mark_build_plan_posted, save_build_plan

        await save_build_plan("TASK-2", "My build plan")
        found = await get_build_plan("TASK-2")
        assert found is not None
        assert found.posted_to_linear is False

        await mark_build_plan_posted("TASK-2")
        found = await get_build_plan("TASK-2")
        assert found is not None
        assert found.posted_to_linear is True

    @pytest.mark.asyncio
    async def test_save_build_plan_updates_existing(self):
        from demetra.services.database import get_build_plan, save_build_plan

        await save_build_plan("TASK-3", "Original plan")
        await save_build_plan("TASK-3", "Updated plan")

        found = await get_build_plan("TASK-3")
        assert found is not None
        assert found.plan_content == "Updated plan"
        assert found.posted_to_linear is False

    @pytest.mark.asyncio
    async def test_save_build_plan_preserves_posted_to_linear(self):
        from demetra.services.database import get_build_plan, mark_build_plan_posted, save_build_plan

        await save_build_plan("TASK-4", "Plan A")
        await mark_build_plan_posted("TASK-4")

        await save_build_plan("TASK-4", "Plan B")
        found = await get_build_plan("TASK-4")
        assert found is not None
        assert found.plan_content == "Plan B"
        assert found.posted_to_linear is True
