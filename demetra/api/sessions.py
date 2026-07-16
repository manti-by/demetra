from typing import Annotated, get_args

from fastapi import APIRouter, Cookie, HTTPException, Query
from fastapi import Path as PathParam

from demetra.library.models import StepType
from demetra.services.auth import get_current_user
from demetra.services.database import delete_session, get_sessions


router = APIRouter(prefix="/api/v1/sessions")

TASK_ID_PATTERN = r"^[A-Za-z0-9_\-]+$"

VALID_STEPS = set(get_args(StepType))


@router.get("")
async def list_sessions(
    auth_token: str | None = Cookie(default=None),
    step: str | None = Query(default=None),
) -> list[dict]:
    """List processing sessions for the authenticated user.

    Returns a list of session records with their current step and metadata.
    """
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    if step is not None and step not in VALID_STEPS:
        raise HTTPException(status_code=400, detail=f"Invalid step. Must be one of: {', '.join(VALID_STEPS)}")

    sessions = await get_sessions(user_id=user.id, step=step)
    return sessions


@router.delete("/{task_id}")
async def delete_session_endpoint(
    task_id: Annotated[str, PathParam(pattern=TASK_ID_PATTERN)],
    auth_token: str | None = Cookie(default=None),
) -> dict:
    """Delete a session and all related data (db record, log files)."""
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    deleted = await delete_session(task_id=task_id, user_id=user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"success": True}
