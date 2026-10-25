from uuid import uuid4

import pytest
from sqlalchemy import text

from demetra.library.models import TokenUsage, ToolUsage
from demetra.services.persistence.database import (
    create_session,
    delete_session,
    get_connection,
    get_pending_session_task_ids,
    get_session,
    get_session_history,
    get_session_id_by_task_id,
    get_session_state,
    get_sessions,
    invalidate_agent_sessions,
    record_agent_invocation,
    record_session_step,
    update_session_is_research,
    update_session_step,
    upsert_pending_session,
)


def _unique_task_id() -> str:
    return f"task-{uuid4().hex[:8]}"


def _unique_session_id() -> str:
    return f"session-{uuid4().hex[:8]}"


async def _fetch_agent_sessions(task_id: str) -> dict[str, dict]:
    async with get_connection() as connection:
        result = await connection.execute(
            text(
                """
                SELECT session_id, step, agent, model, fork_of, is_primary,
                       cursor_input, cursor_output, cursor_cost
                  FROM agent_sessions
                 WHERE task_id = :task_id
                """
            ),
            {"task_id": task_id},
        )
        return {row.session_id: dict(row._mapping) for row in result.fetchall()}


async def _fetch_tool_usage(task_id: str) -> dict[str, dict]:
    async with get_connection() as connection:
        result = await connection.execute(
            text(
                """
                SELECT step, tool_name, calls, succeeded, failed, duration_ms
                  FROM session_tool_usage
                 WHERE task_id = :task_id
                 ORDER BY tool_name
                """
            ),
            {"task_id": task_id},
        )
        return {row.tool_name: dict(row._mapping) for row in result.fetchall()}


class TestUpdateSessionStep:
    @pytest.mark.asyncio
    async def test_advances_step_without_writing_history(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await upsert_pending_session(task_id=task_id, session_id=session_id)

        await update_session_step(task_id=task_id, step="build")

        state = await get_session_state(task_id)
        assert state is not None
        assert state.step == "build"
        assert await get_session_history(task_id=task_id) == []


class TestRecordSessionStep:
    @pytest.mark.asyncio
    async def test_records_a_step_row_without_tokens(self):
        task_id = _unique_task_id()

        entry = await record_session_step(task_id=task_id, step="completed")

        assert entry.kind == "step"
        assert entry.session_id is None
        assert entry.length is None
        history = await get_session_history(task_id=task_id)
        assert [row.kind for row in history] == ["step"]
        assert history[0].step == "completed"

    @pytest.mark.asyncio
    async def test_upserts_the_same_step_once(self):
        task_id = _unique_task_id()

        first = await record_session_step(task_id=task_id, step="awaiting_input")
        second = await record_session_step(task_id=task_id, step="awaiting_input")

        assert first.id == second.id
        assert len(await get_session_history(task_id=task_id)) == 1

    @pytest.mark.asyncio
    async def test_keeps_distinct_steps(self):
        task_id = _unique_task_id()

        await record_session_step(task_id=task_id, step="plan")
        await record_session_step(task_id=task_id, step="completed")

        steps = [row.step for row in await get_session_history(task_id=task_id)]
        assert steps == ["plan", "completed"]


class TestRecordAgentInvocation:
    @pytest.mark.asyncio
    async def test_first_invocation_records_full_cumulative_as_delta(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()

        entry = await record_agent_invocation(
            task_id=task_id,
            step="build",
            session_id=session_id,
            usage=TokenUsage(input=1000, output=500, cache_read=200),
            agent="build",
            model="provider/model",
        )

        assert entry.kind == "invocation"
        assert entry.agent_session_id is not None
        assert entry.input_tokens == 1000
        assert entry.output_tokens == 500
        assert entry.cache_read_tokens == 200
        assert entry.length == 1700
        assert entry.agent == "build"
        assert entry.model == "provider/model"

    @pytest.mark.asyncio
    async def test_second_invocation_accumulates_its_delta_and_upserts(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=1000)
        )

        entry = await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=1500)
        )

        assert entry.input_tokens == 1500
        history = await get_session_history(task_id=task_id)
        assert len(history) == 1
        assert history[0].input_tokens == 1500

    @pytest.mark.asyncio
    async def test_delta_is_never_negative_when_cumulative_shrinks(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=2000)
        )

        entry = await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=500)
        )

        assert entry.input_tokens == 2000

    @pytest.mark.asyncio
    async def test_cursor_stays_monotonic_across_a_compaction_bump(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        first = await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=25_343)
        )
        second = await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=61_610)
        )
        third = await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=79_942)
        )

        assert first.input_tokens == 25_343
        assert second.input_tokens == 61_610
        assert third.input_tokens == 79_942
        assert (await _fetch_agent_sessions(task_id))[session_id]["cursor_input"] == 79_942

    @pytest.mark.asyncio
    async def test_failed_export_keeps_prior_tokens_and_cursor(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=1000)
        )

        await record_agent_invocation(task_id=task_id, step="build", session_id=session_id, usage=None)

        history = await get_session_history(task_id=task_id)
        assert history[0].input_tokens == 1000

        entry = await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=1200)
        )
        assert entry.input_tokens == 1200

    @pytest.mark.asyncio
    async def test_fork_restarts_cursor_from_parent_session(self):
        task_id = _unique_task_id()
        parent_session_id = _unique_session_id()
        fork_session_id = _unique_session_id()
        await record_agent_invocation(
            task_id=task_id, step="plan", session_id=parent_session_id, usage=TokenUsage(input=5000)
        )

        entry = await record_agent_invocation(
            task_id=task_id,
            step="build",
            session_id=fork_session_id,
            usage=TokenUsage(input=1000),
            fork_of=parent_session_id,
        )

        assert entry.input_tokens == 1000

    @pytest.mark.asyncio
    async def test_same_session_distinct_steps_get_distinct_rows(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()

        await record_agent_invocation(task_id=task_id, step="plan", session_id=session_id, usage=TokenUsage(input=100))
        await record_agent_invocation(task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=150))

        history = await get_session_history(task_id=task_id)
        assert [(row.step, row.input_tokens) for row in history] == [("plan", 100), ("build", 50)]

    @pytest.mark.asyncio
    async def test_cost_delta_is_recorded(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=100), cost=0.25
        )

        entry = await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=200), cost=0.40
        )

        assert entry.cost == pytest.approx(0.40)

    @pytest.mark.asyncio
    async def test_primary_records_session_pointer_and_clears_previous(self):
        task_id = _unique_task_id()
        await upsert_pending_session(task_id=task_id, session_id="session-first")

        await record_agent_invocation(
            task_id=task_id,
            step="plan",
            session_id="session-first",
            usage=TokenUsage(input=100),
            is_primary=True,
        )
        assert await get_session_id_by_task_id(task_id) == "session-first"

        await record_agent_invocation(
            task_id=task_id,
            step="build",
            session_id="session-second",
            usage=TokenUsage(input=100),
            is_primary=True,
        )
        assert await get_session_id_by_task_id(task_id) == "session-second"

    @pytest.mark.asyncio
    async def test_invalidate_clears_primary_marker_but_keeps_history(self):
        task_id = _unique_task_id()
        await upsert_pending_session(task_id=task_id, session_id="session-first")
        await record_agent_invocation(
            task_id=task_id,
            step="build",
            session_id="session-first",
            usage=TokenUsage(input=100),
            is_primary=True,
        )

        await invalidate_agent_sessions(task_id=task_id)

        history = await get_session_history(task_id=task_id)
        assert len(history) == 1
        assert history[0].input_tokens == 100


class TestAgentSessions:
    @pytest.mark.asyncio
    async def test_cursor_advances_across_invocations(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=1000, output=200)
        )

        entry = await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=1500, output=300)
        )

        assert entry.input_tokens == 1500
        assert entry.output_tokens == 300
        sessions = await _fetch_agent_sessions(task_id)
        assert sessions[session_id]["cursor_input"] == 1500
        assert sessions[session_id]["cursor_output"] == 300

    @pytest.mark.asyncio
    async def test_resumed_session_keeps_one_row(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await record_agent_invocation(task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=100))
        await record_agent_invocation(task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=200))

        assert list((await _fetch_agent_sessions(task_id)).keys()) == [session_id]

    @pytest.mark.asyncio
    async def test_fork_records_lineage_without_seeding_cursor(self):
        task_id = _unique_task_id()
        parent_session_id = _unique_session_id()
        fork_session_id = _unique_session_id()
        await record_agent_invocation(
            task_id=task_id, step="plan", session_id=parent_session_id, usage=TokenUsage(input=5000)
        )

        entry = await record_agent_invocation(
            task_id=task_id,
            step="build",
            session_id=fork_session_id,
            usage=TokenUsage(input=1000),
            fork_of=parent_session_id,
        )

        assert entry.input_tokens == 1000
        sessions = await _fetch_agent_sessions(task_id)
        assert sessions[fork_session_id]["fork_of"] == parent_session_id
        assert sessions[fork_session_id]["cursor_input"] == 1000

    @pytest.mark.asyncio
    async def test_only_one_primary_row_per_task(self):
        task_id = _unique_task_id()
        await record_agent_invocation(
            task_id=task_id, step="plan", session_id=_unique_session_id(), usage=TokenUsage(input=100), is_primary=True
        )
        second = _unique_session_id()
        await record_agent_invocation(
            task_id=task_id, step="build", session_id=second, usage=TokenUsage(input=100), is_primary=True
        )

        sessions = await _fetch_agent_sessions(task_id)
        primaries = [session_id for session_id, row in sessions.items() if row["is_primary"]]
        assert primaries == [second]

    @pytest.mark.asyncio
    async def test_failed_export_does_not_advance_the_cursor(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=1000)
        )

        await record_agent_invocation(task_id=task_id, step="build", session_id=session_id, usage=None)

        assert (await _fetch_agent_sessions(task_id))[session_id]["cursor_input"] == 1000


class TestAgentAttribution:
    @pytest.mark.asyncio
    async def test_agent_and_serialized_model_persisted(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()

        entry = await record_agent_invocation(
            task_id=task_id,
            step="review",
            session_id=session_id,
            usage=TokenUsage(input=100),
            agent="review-agent",
            model="anthropic/claude-sonnet-4#thinking",
        )

        assert entry.agent == "review-agent"
        assert entry.model == "anthropic/claude-sonnet-4#thinking"
        session = (await _fetch_agent_sessions(task_id))[session_id]
        assert session["agent"] == "review-agent"
        assert session["model"] == "anthropic/claude-sonnet-4#thinking"

    @pytest.mark.asyncio
    async def test_missing_attribution_does_not_clear_previous_values(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await record_agent_invocation(
            task_id=task_id,
            step="build",
            session_id=session_id,
            usage=TokenUsage(input=100),
            agent="build-agent",
            model="provider/model",
        )

        await record_agent_invocation(task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=200))

        session = (await _fetch_agent_sessions(task_id))[session_id]
        assert session["agent"] == "build-agent"
        assert session["model"] == "provider/model"

    @pytest.mark.asyncio
    async def test_review_rounds_and_models_get_distinct_rows(self):
        task_id = _unique_task_id()
        await record_agent_invocation(
            task_id=task_id,
            step="review",
            session_id=_unique_session_id(),
            usage=TokenUsage(input=100),
            agent="review-agent",
            model="provider/a",
        )
        await record_agent_invocation(
            task_id=task_id,
            step="review",
            session_id=_unique_session_id(),
            usage=TokenUsage(input=100),
            agent="review-agent",
            model="provider/b",
        )

        history = await get_session_history(task_id=task_id)
        assert sorted(row.model or "" for row in history) == ["provider/a", "provider/b"]


class TestAgentSessionPending:
    @pytest.mark.asyncio
    async def test_task_is_pending_until_an_invocation_is_recorded(self):
        task_id = _unique_task_id()
        await upsert_pending_session(task_id=task_id, session_id=_unique_session_id())

        assert task_id in await get_pending_session_task_ids()

        await record_agent_invocation(
            task_id=task_id, step="build", session_id=_unique_session_id(), usage=TokenUsage(input=100)
        )

        assert task_id not in await get_pending_session_task_ids()


class TestSessionHistoryKind:
    @pytest.mark.asyncio
    async def test_step_and_invocation_rows_coexist_in_order(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await upsert_pending_session(task_id=task_id, session_id=session_id)

        await update_session_step(task_id=task_id, step="build")
        await record_agent_invocation(task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=100))
        await record_session_step(task_id=task_id, step="completed")

        history = await get_session_history(task_id=task_id)
        assert [row.kind for row in history] == ["invocation", "step"]
        assert history[0].task_id == task_id
        assert history[1].agent_session_id is None


class TestRecordToolUsage:
    @pytest.mark.asyncio
    async def test_first_invocation_inserts_per_tool_rows(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()

        entry = await record_agent_invocation(
            task_id=task_id,
            step="build",
            session_id=session_id,
            usage=TokenUsage(input=100),
            tool_usage={
                "bash": ToolUsage(name="bash", calls=3, succeeded=2, failed=1, duration_ms=70),
                "read": ToolUsage(name="read", calls=1, succeeded=1, duration_ms=5),
            },
        )

        rows = await _fetch_tool_usage(task_id)
        assert rows["bash"]["step"] == "build"
        assert rows["bash"]["calls"] == 3
        assert rows["bash"]["succeeded"] == 2
        assert rows["bash"]["failed"] == 1
        assert rows["bash"]["duration_ms"] == 70
        assert rows["read"]["calls"] == 1
        assert {usage.name: usage.calls for usage in entry.tool_usage} == {"bash": 3, "read": 1}

    @pytest.mark.asyncio
    async def test_second_invocation_accumulates_counts(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await record_agent_invocation(
            task_id=task_id,
            step="build",
            session_id=session_id,
            usage=TokenUsage(input=100),
            tool_usage={"bash": ToolUsage(name="bash", calls=2, succeeded=2, duration_ms=20)},
        )

        entry = await record_agent_invocation(
            task_id=task_id,
            step="build",
            session_id=session_id,
            usage=TokenUsage(input=200),
            tool_usage={"bash": ToolUsage(name="bash", calls=3, succeeded=1, failed=2, duration_ms=45)},
        )

        row = (await _fetch_tool_usage(task_id))["bash"]
        assert row["calls"] == 5
        assert row["succeeded"] == 3
        assert row["failed"] == 2
        assert row["duration_ms"] == 65
        assert entry.tool_usage == [ToolUsage(name="bash", calls=5, succeeded=3, failed=2, duration_ms=65)]

    @pytest.mark.asyncio
    async def test_failed_export_leaves_tool_rows_untouched(self):
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await record_agent_invocation(
            task_id=task_id,
            step="build",
            session_id=session_id,
            usage=TokenUsage(input=100),
            tool_usage={"bash": ToolUsage(name="bash", calls=2)},
        )

        entry = await record_agent_invocation(
            task_id=task_id, step="build", session_id=session_id, usage=None, tool_usage=None
        )

        assert (await _fetch_tool_usage(task_id))["bash"]["calls"] == 2
        assert entry.tool_usage == []

    @pytest.mark.asyncio
    async def test_history_attaches_tool_usage_per_step(self):
        task_id = _unique_task_id()
        build_session = _unique_session_id()
        validate_session = _unique_session_id()
        await record_agent_invocation(
            task_id=task_id,
            step="build",
            session_id=build_session,
            usage=TokenUsage(input=100),
            tool_usage={"bash": ToolUsage(name="bash", calls=2)},
        )
        await record_agent_invocation(
            task_id=task_id,
            step="validate",
            session_id=validate_session,
            usage=TokenUsage(input=100),
            tool_usage={"read": ToolUsage(name="read", calls=1)},
        )
        await record_session_step(task_id=task_id, step="completed")

        history = await get_session_history(task_id=task_id)

        by_step = {row.step: row for row in history}
        assert [usage.name for usage in by_step["build"].tool_usage] == ["bash"]
        assert [usage.name for usage in by_step["validate"].tool_usage] == ["read"]
        assert by_step["completed"].tool_usage == []

    @pytest.mark.asyncio
    async def test_delete_session_removes_tool_usage(self):
        user_id = str(uuid4())
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await upsert_pending_session(task_id=task_id, session_id=session_id, user_id=user_id)
        await record_agent_invocation(
            task_id=task_id,
            step="build",
            session_id=session_id,
            usage=TokenUsage(input=100),
            tool_usage={"bash": ToolUsage(name="bash", calls=2)},
        )

        assert await delete_session(task_id=task_id, user_id=user_id) is True

        assert await _fetch_tool_usage(task_id) == {}


class TestGetSessionsHasHistory:
    @pytest.mark.asyncio
    async def test_has_history_reflects_any_history_row(self):
        user_id = str(uuid4())
        task_with_history = _unique_task_id()
        task_without_history = _unique_task_id()
        await upsert_pending_session(task_id=task_with_history, session_id=_unique_session_id(), user_id=user_id)
        await upsert_pending_session(task_id=task_without_history, session_id=_unique_session_id(), user_id=user_id)
        await record_agent_invocation(
            task_id=task_with_history,
            step="build",
            session_id=_unique_session_id(),
            usage=TokenUsage(input=100),
        )

        rows = {row["task_id"]: row for row in await get_sessions(user_id=user_id)}

        assert rows[task_with_history]["has_history"] is True
        assert rows[task_without_history]["has_history"] is False


class TestDeleteSessionCascade:
    @pytest.mark.asyncio
    async def test_delete_removes_history_and_agent_sessions(self):
        user_id = str(uuid4())
        task_id = _unique_task_id()
        session_id = _unique_session_id()
        await upsert_pending_session(task_id=task_id, session_id=session_id, user_id=user_id)
        await record_agent_invocation(task_id=task_id, step="build", session_id=session_id, usage=TokenUsage(input=100))
        await record_session_step(task_id=task_id, step="completed")

        deleted = await delete_session(task_id=task_id, user_id=user_id)

        assert deleted is True
        assert await get_session_history(task_id=task_id) == []
        assert await get_session(task_id) is None


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
