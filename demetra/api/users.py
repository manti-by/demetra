"""User management endpoints."""

from fastapi import APIRouter, Cookie, HTTPException

from demetra.library.models import UserKeysUpdateRequest
from demetra.services.auth import get_current_user
from demetra.services.database import update_user_keys


router = APIRouter()


@router.patch("/api/v1/users/me/keys")
async def update_user_keys_endpoint(
    request: UserKeysUpdateRequest,
    auth_token: str | None = Cookie(default=None),
):
    """Update API keys for the authenticated user.

    Accepts a dictionary of key-value pairs to store as the user's
    API keys. These keys are typically used for external service integrations.
    """
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    await update_user_keys(user_id=user.id, keys=request.keys)
    return {"message": "Keys updated successfully"}
