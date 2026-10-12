from uuid import uuid4

import pytest

from demetra.services.persistence.database import (
    create_session,
    get_session,
    get_session_history,
    get_session_state,
    update_session_is_research,
    update_session_step,
    upsert_pending_session,
)


def _unique_task_id() -> str:
    return f"task-{uuid4().hex[:8]}"


def _unique_session_id() -> str:
    return f"session-{uuid4().hex[:8]}"


class TestUpdateSessionStepHistory:
    @pytest.mark.asyncio
    async def test_with_session_id_writes_step_only_history_row(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await upsert_pending_session(task_id=task_id, session_id=session_id)

        await update_session_step(task_id=task_id, step="build", session_id=session_id)

        history = await get_session_history(session_id=session_id)

        assert len(history) == 1
        entry = history[0]
        assert entry.session_id == session_id
        assert entry.step == "build"
        assert entry.length is None
        assert entry.input_tokens is None
        assert entry.output_tokens is None
        assert entry.reasoning_tokens is None
        assert entry.cache_read_tokens is None
        assert entry.cache_write_tokens is None
        assert entry.context_tokens is None
        assert entry.model is None

    @pytest.mark.asyncio
    async def test_without_session_id_skips_history_insertion(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await upsert_pending_session(task_id=task_id, session_id=session_id)

        await update_session_step(task_id=task_id, step="build")

        assert await get_session_history(session_id=session_id) == []

    @pytest.mark.asyncio
    async def test_sequential_updates_persist_in_creation_order(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await upsert_pending_session(task_id=task_id, session_id=session_id)

        await update_session_step(task_id=task_id, step="plan", session_id=session_id)
        await update_session_step(task_id=task_id, step="build", session_id=session_id)
        await update_session_step(task_id=task_id, step="review", session_id=session_id)

        history = await get_session_history(session_id=session_id)

        assert [entry.step for entry in history] == ["plan", "build", "review"]


class TestGetSessionState:
    @pytest.mark.asyncio
    async def test_returns_step_name_and_research_flag(self, db_task_id: str, db_session_id: str):
        await create_session(db_task_id, db_session_id)

        result = await get_session_state(db_task_id)
        assert result is not None
        assert result.step == "initial"
        assert result.name == ""
        assert result.is_research is False

        await update_session_step(task_id=db_task_id, step="build")
        result = await get_session_state(db_task_id)
        assert result is not None
        assert result.step == "build"

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_task(self):
        result = await get_session_state("nonexistent-task")

        assert result is None

    @pytest.mark.asyncio
    async def test_scopes_by_user_id(self, db_task_id: str, db_session_id: str):
        await upsert_pending_session(
            task_id=db_task_id,
            session_id=db_session_id,
            user_id="owner-user",
            name="Owner Session",
        )

        result = await get_session_state(task_id=db_task_id, user_id="owner-user")
        assert result is not None
        assert result.step == "initial"
        assert result.name == "Owner Session"

        result = await get_session_state(task_id=db_task_id, user_id="other-user")
        assert result is None


class TestUpdateSessionIsResearch:
    @pytest.mark.asyncio
    async def test_toggles_research_flag(self, db_task_id: str, db_session_id: str):
        await create_session(db_task_id, db_session_id)

        found = await get_session(db_task_id)
        assert found is not None
        assert found.is_research is False

        await update_session_is_research(task_id=db_task_id, is_research=True)
        found = await get_session(db_task_id)
        assert found is not None
        assert found.is_research is True

        state = await get_session_state(db_task_id)
        assert state is not None
        assert state.is_research is True

        await update_session_is_research(task_id=db_task_id, is_research=False)
        state = await get_session_state(db_task_id)
        assert state is not None
        assert state.is_research is False

    @pytest.mark.asyncio
    async def test_upsert_pending_session_returns_stored_research_flag(self, db_task_id: str, db_session_id: str):
        await create_session(db_task_id, db_session_id)
        await update_session_is_research(task_id=db_task_id, is_research=True)

        session = await upsert_pending_session(task_id=db_task_id, session_id=db_session_id)

        assert session.is_research is True
        assert session.step == "initial"
