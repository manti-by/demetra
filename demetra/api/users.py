from fastapi import APIRouter, Depends, HTTPException

from demetra.library.env import ENV_KEY_RE, MAX_ENV_KEY_LENGTH, MAX_ENV_VALUE_LENGTH
from demetra.library.models import EnvironmentEntry, EnvironmentUpsert, UserKeysUpdateRequest, UserResponse
from demetra.services.auth import get_current_user_dep
from demetra.services.persistence.database import (
    delete_user_environment,
    list_user_environments,
    update_user_keys,
    upsert_user_environment,
)


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


@router.get("/me/env", response_model=list[EnvironmentEntry])
async def list_user_environment_endpoint(
    user: UserResponse = Depends(get_current_user_dep),
) -> list[EnvironmentEntry]:
    """List the authenticated user's shared environment variables.

    User-shared env is applied to every project the user owns or
    collaborates on. Encrypted values are returned masked.
    """
    entries = await list_user_environments(user_id=user.id)
    return [
        EnvironmentEntry(
            id=entry["id"],
            key=entry["key"],
            value=entry["value"],
            type=entry["type"],
            scope="user",
            user_id=user.id,
        )
        for entry in entries
    ]


@router.put("/me/env/{key}", response_model=EnvironmentEntry)
async def upsert_user_environment_endpoint(
    key: str,
    request: EnvironmentUpsert,
    user: UserResponse = Depends(get_current_user_dep),
) -> EnvironmentEntry:
    """Create or update a single shared environment variable for the current user.

    The value applies to every project the user owns or collaborates on.
    Encrypted values are stored encrypted and returned masked.
    """
    validated_key = key.strip()
    if not validated_key:
        raise HTTPException(status_code=400, detail="Environment key cannot be empty")
    if len(validated_key) > MAX_ENV_KEY_LENGTH:
        raise HTTPException(status_code=400, detail="Environment key must be at most 128 characters")
    if not ENV_KEY_RE.fullmatch(validated_key):
        raise HTTPException(status_code=400, detail="Environment key must match [A-Za-z_][A-Za-z0-9_.-]*")

    if request.type not in ("text", "encrypted"):
        raise HTTPException(status_code=400, detail="Environment type must be 'text' or 'encrypted'")

    if len(request.value) > MAX_ENV_VALUE_LENGTH:
        raise HTTPException(status_code=400, detail="Environment value must be at most 8192 characters")

    if request.type == "text" and "\x00" in request.value:
        raise HTTPException(status_code=400, detail="Environment value cannot contain NUL bytes")

    try:
        entry = await upsert_user_environment(
            user_id=user.id,
            key=validated_key,
            value=request.value,
            env_type=request.type,
            previous_key=request.previous_key.strip() if request.previous_key else None,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail="User not found") from e

    return EnvironmentEntry(
        id=entry["id"],
        key=entry["key"],
        value=entry["value"],
        type=entry["type"],
        scope="user",
        user_id=entry["user_id"],
    )


@router.delete("/me/env/{key}")
async def delete_user_environment_endpoint(
    key: str,
    user: UserResponse = Depends(get_current_user_dep),
) -> dict[str, str]:
    """Delete a shared environment variable for the current user."""
    validated_key = key.strip()
    if not validated_key:
        raise HTTPException(status_code=400, detail="Environment key cannot be empty")

    try:
        await delete_user_environment(user_id=user.id, key=validated_key)
    except LookupError as e:
        raise HTTPException(status_code=404, detail="User not found") from e

    return {"message": "Environment variable deleted successfully"}
