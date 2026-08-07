from fastapi import APIRouter, Depends

from demetra.library.models import UserKeysUpdateRequest, UserResponse
from demetra.services.auth import get_current_user_dep
from demetra.services.persistence.database import update_user_keys


router = APIRouter(prefix="/api/v1/users")


@router.patch("/me/keys")
async def update_user_keys_endpoint(
    request: UserKeysUpdateRequest,
    user: UserResponse = Depends(get_current_user_dep),
):
    """Update API keys for the authenticated user.

    Accepts a dictionary of key-value pairs to store as the user's
    API keys. These keys are typically used for external service integrations.
    """
    await update_user_keys(user_id=user.id, keys=request.keys)
    return {"message": "Keys updated successfully"}
