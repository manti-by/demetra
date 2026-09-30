from uuid import uuid4

import pytest

from demetra.services.persistence.database import get_session_history, update_session_step, upsert_pending_session


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
