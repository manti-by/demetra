from typing import Annotated, get_args

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam

from demetra.library.models import SessionHistory, StepType, UserResponse
from demetra.services.auth import get_current_user_dep
from demetra.services.persistence.database import (
    delete_session,
    get_session_history,
    get_session_state,
    get_sessions,
)


router = APIRouter(prefix="/api/v1/sessions")

TASK_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"

VALID_STEPS = set(get_args(StepType))


@router.get("")
async def list_sessions(
    user: UserResponse = Depends(get_current_user_dep),
    step: str | None = Query(default=None),
) -> list[dict]:
    """List processing sessions for the authenticated user.

    Returns a list of session records with their current step and metadata.
    """
    if step is not None and step not in VALID_STEPS:
        raise HTTPException(status_code=400, detail=f"Invalid step. Must be one of: {', '.join(VALID_STEPS)}")

    sessions = await get_sessions(user_id=user.id, step=step)
    return sessions


@router.delete("/{task_id}")
async def delete_session_endpoint(
    task_id: Annotated[str, PathParam(pattern=TASK_ID_PATTERN)],
    user: UserResponse = Depends(get_current_user_dep),
) -> dict:
    """Delete a session and all related data (db record, log files)."""
    deleted = await delete_session(task_id=task_id, user_id=user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"success": True}


@router.get("/{task_id}/history")
async def get_session_history_endpoint(
    task_id: Annotated[str, PathParam(pattern=TASK_ID_PATTERN)],
    user: UserResponse = Depends(get_current_user_dep),
) -> dict:
    """Return the history of recorded step and invocation runs for a session.

    History resolves by ``task_id`` rather than the display-only
    ``sessions.session_id`` pointer, so a task whose worktree (and session) was
    removed still exposes its full history.

    Args:
        task_id: Identifier of the session's task.
        user: The authenticated user.

    Returns:
        dict: A mapping with the session-wide token totals under ``total``,
            the session-wide per-tool call counts under ``tool_usage``, and the
            serialized session history rows under ``history``.

    Raises:
        HTTPException: 404 when no session exists for the task.
    """
    state = await get_session_state(task_id=task_id, user_id=user.id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    rows = await get_session_history(task_id=task_id)
    return {
        "total": _compute_total_tokens(rows=rows),
        "tool_usage": _compute_tool_usage(rows=rows),
        "history": [_serialize_history_row(row=r) for r in rows],
    }


def _compute_total_tokens(rows: list[SessionHistory]) -> dict:
    """Sum all counter fields across invocation history records.

    Only ``kind='invocation'`` rows carry exact per-invocation deltas and are
    summed; ``kind='step'`` rows are informational milestones with no tokens.
    ``context_tokens`` is a per-invocation snapshot of the context window, not a
    usage counter, so it is excluded from the sum. ``length`` is derived from
    the summed token fields to keep it consistent with the breakdown.

    Args:
        rows: The session history records to sum.

    Returns:
        dict: The session-wide totals for every counter field, plus the summed ``cost``.
    """
    total = {
        "length": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "cost": 0.0,
    }
    for row in rows:
        if row.kind != "invocation":
            continue
        total["input_tokens"] += row.input_tokens or 0
        total["output_tokens"] += row.output_tokens or 0
        total["reasoning_tokens"] += row.reasoning_tokens or 0
        total["cache_read_tokens"] += row.cache_read_tokens or 0
        total["cache_write_tokens"] += row.cache_write_tokens or 0
        total["cost"] += row.cost or 0.0
        total["length"] += (
            (row.input_tokens or 0)
            + (row.output_tokens or 0)
            + (row.reasoning_tokens or 0)
            + (row.cache_read_tokens or 0)
            + (row.cache_write_tokens or 0)
        )
    return total


def _compute_tool_usage(rows: list[SessionHistory]) -> list[dict]:
    """Merge the per-tool call counts across invocation history records.

    Only ``kind='invocation'`` rows carry tool usage; every invocation row is a
    distinct slice whose counts were already filtered by its invocation
    watermark, so merging them cannot double count. The result is ordered by
    call count and then tool name so the frontend renders a stable breakdown.

    Args:
        rows: The session history records to merge.

    Returns:
        list[dict]: One entry per tool name, with its merged counters.
    """
    merged: dict[str, dict] = {}
    for row in rows:
        if row.kind != "invocation":
            continue
        for usage in row.tool_usage:
            entry = merged.setdefault(
                usage.name,
                {"name": usage.name, "calls": 0, "succeeded": 0, "failed": 0, "duration_ms": 0},
            )
            entry["calls"] += usage.calls
            entry["succeeded"] += usage.succeeded
            entry["failed"] += usage.failed
            entry["duration_ms"] += usage.duration_ms
    return sorted(merged.values(), key=lambda entry: (-entry["calls"], entry["name"]))


def _serialize_history_row(row: SessionHistory) -> dict:
    """Convert a session history record into its JSON representation.

    Args:
        row: The SessionHistory record to serialize.

    Returns:
        dict: The history row with all public fields.
    """
    return {
        "id": row.id,
        "session_id": row.session_id,
        "task_id": row.task_id,
        "agent_session_id": row.agent_session_id,
        "kind": row.kind,
        "step": row.step,
        "length": row.length,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "reasoning_tokens": row.reasoning_tokens,
        "cache_read_tokens": row.cache_read_tokens,
        "cache_write_tokens": row.cache_write_tokens,
        "context_tokens": row.context_tokens,
        "cost": row.cost,
        "model": row.model,
        "agent": row.agent,
        "tool_usage": [
            {
                "name": usage.name,
                "calls": usage.calls,
                "succeeded": usage.succeeded,
                "failed": usage.failed,
                "duration_ms": usage.duration_ms,
            }
            for usage in row.tool_usage
        ],
        "message": row.message,
        "created_at": row.created_at,
    }
