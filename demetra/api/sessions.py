from typing import Annotated, get_args

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam

from demetra.library.models import SessionHistory, StepType, UserResponse
from demetra.services.auth import get_current_user_dep
from demetra.services.database import (
    delete_session,
    get_session_history,
    get_session_id_by_task_id,
    get_sessions,
)


router = APIRouter(prefix="/api/v1/sessions")

TASK_ID_PATTERN = r"^[A-Za-z0-9_\-]+$"

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
) -> list[dict]:
    session_id = await get_session_id_by_task_id(task_id=task_id, user_id=user.id)
    if session_id is None:
        raise HTTPException(status_code=404, detail="Session not found")

    rows = await get_session_history(session_id=session_id)
    return [_serialize_history_row(r) for r in rows]


def _serialize_history_row(row: SessionHistory) -> dict:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "step": row.step,
        "length": row.length,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "reasoning_tokens": row.reasoning_tokens,
        "cache_read_tokens": row.cache_read_tokens,
        "cache_write_tokens": row.cache_write_tokens,
        "context_tokens": row.context_tokens,
        "model": row.model,
        "created_at": row.created_at,
    }
