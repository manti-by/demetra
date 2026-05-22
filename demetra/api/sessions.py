from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Query

from demetra.services.auth import get_current_user
from demetra.services.database import get_sessions


router = APIRouter(prefix="/api/v1/sessions")


@router.get("")
async def list_sessions(
    auth_token: str | None = Cookie(default=None),
    status: Annotated[str | None, Query()] = None,
) -> list[dict]:
    """List processing sessions for the authenticated user.

    Optionally filter by status (pending, processed, failed).
    Returns a list of session records with their current state and metadata.
    """
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    if status and status not in ("pending", "processed", "failed"):
        raise HTTPException(status_code=400, detail="Invalid status. Must be one of: pending, processed, failed")

    sessions = await get_sessions(user_id=user.id, status=status)
    return sessions
