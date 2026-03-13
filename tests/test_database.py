import pytest


class TestDatabaseService:
    @pytest.mark.asyncio
    async def test_create_and_read(
        self,
        db_task_id: str,
        db_session_id: str,
    ):
        from demetra.services.database import create_session, get_session

        record = await create_session(db_task_id, db_session_id)
        assert record.task_id == db_task_id
        assert record.session_id == db_session_id
        assert record.build_plan == ""
        assert record.posted_to_linear is False

        found = await get_session(db_task_id)
        assert found is not None
        assert found.task_id == db_task_id
        assert found.session_id == db_session_id

    @pytest.mark.asyncio
    async def test_read_nonexistent(self):
        from demetra.services.database import get_session

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

        session = await save_session(db_task_id, db_session_id, db_build_plan)
        assert session.task_id == db_task_id
        assert session.session_id == db_session_id
        assert session.build_plan == db_build_plan
        assert session.posted_to_linear is False

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

        await save_session(db_task_id, db_session_id, "Original plan")
        await save_session(db_task_id, f"session-{db_session_id}", "Updated plan")

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

        await save_session(db_task_id, db_session_id, "Plan A")
        await mark_session_posted(db_task_id)
        await save_session(db_task_id, f"session-{db_session_id}", "Plan B")

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

        await save_session(db_task_id, db_session_id, "My build plan")

        found = await get_session(db_task_id)
        assert found is not None
        assert found.posted_to_linear is False

        await mark_session_posted(db_task_id)
        found = await get_session(db_task_id)
        assert found is not None
        assert found.posted_to_linear is True
