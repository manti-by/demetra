import secrets
from datetime import UTC, datetime, timedelta

import aiohttp
from jose import JWTError, jwt

from demetra.library.exceptions import LinearError
from demetra.library.models import AuthResponse, GitHubUser, TokenData, UserResponse
from demetra.services.database import (
    create_user,
    delete_jwt_token,
    get_jwt_token,
    get_user_by_github_id,
    get_user_by_id,
    save_jwt_token,
)
from demetra.settings import GITHUB, JWT


class AuthError(LinearError):
    pass


def get_github_auth_url() -> tuple[str, str]:
    state = secrets.token_urlsafe(32)
    oauth = GITHUB["oauth"]
    params = {
        "client_id": oauth["client_id"],
        "redirect_uri": oauth["redirect_uri"],
        "scope": "read:user user:email",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{oauth['oauth_url']}?{query}", state


async def exchange_code_for_token(code: str) -> str:
    oauth = GITHUB["oauth"]
    if not oauth["client_id"] or not oauth["client_secret"]:
        raise AuthError("GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET must be set")

    payload = {
        "client_id": oauth["client_id"],
        "client_secret": oauth["client_secret"],
        "code": code,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                oauth["token_url"],
                data=payload,
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Accept": "application/json"},
            ) as response:
                response.raise_for_status()
                data = await response.json()

        access_token = data.get("access_token")
        if not access_token:
            raise AuthError("No access token in OAuth response")

        return access_token
    except aiohttp.ClientError as e:
        raise AuthError(f"OAuth token exchange error: {e}") from e


async def get_github_user(access_token: str) -> GitHubUser:
    oauth = GITHUB["oauth"]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                oauth["user_url"],
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Authorization": f"Bearer {access_token}"},
            ) as response:
                response.raise_for_status()
                data = await response.json()

        return GitHubUser(
            id=str(data["id"]),
            login=data["login"],
            email=data.get("email"),
            avatar_url=data.get("avatar_url"),
        )
    except aiohttp.ClientError as e:
        raise AuthError(f"Failed to fetch GitHub user: {e}") from e


def create_jwt_token(user_id: str) -> tuple[str, str]:
    if not JWT["secret_key"]:
        raise AuthError("JWT_SECRET_KEY must be set")

    expires_delta = timedelta(days=JWT["expiration_days"])
    expire = datetime.now(UTC) + expires_delta

    to_encode = {"user_id": user_id, "exp": int(expire.timestamp())}
    token = jwt.encode(to_encode, JWT["secret_key"], algorithm=JWT["algorithm"])

    return token, expire.isoformat()


async def verify_jwt_token(token: str) -> TokenData | None:
    if not JWT["secret_key"]:
        raise AuthError("JWT_SECRET_KEY must be set")

    try:
        payload = jwt.decode(token, JWT["secret_key"], algorithms=[JWT["algorithm"]])

        token_data = await get_jwt_token(token)
        if not token_data:
            return None

        expires_at = token_data["expires_at"]
        if expires_at is None or datetime.now(UTC) > expires_at:
            return None

        return TokenData(user_id=payload["user_id"], exp=payload["exp"])
    except JWTError:
        return None


async def get_or_create_user(github_user: GitHubUser) -> str:
    existing_user = await get_user_by_github_id(github_user.id)
    if existing_user:
        return existing_user["id"]

    return await create_user(
        github_id=github_user.id,
        github_username=github_user.login,
        email=github_user.email,
        avatar_url=github_user.avatar_url,
    )


async def authenticate_user(github_user: GitHubUser) -> AuthResponse:
    user_id = await get_or_create_user(github_user)
    token, expires_at = create_jwt_token(user_id)

    await save_jwt_token(token=token, user_id=user_id, expires_at=expires_at)

    user_data = await get_user_by_id(user_id)
    if not user_data:
        raise AuthError("User not found after creation")

    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user_data["id"],
            github_username=user_data["github_username"],
            email=user_data["email"],
            avatar_url=user_data.get("avatar_url"),
        ),
    )


async def logout(token: str) -> None:
    await delete_jwt_token(token)


async def get_current_user(token: str) -> UserResponse | None:
    token_data = await verify_jwt_token(token)
    if not token_data:
        return None

    user_data = await get_user_by_id(token_data.user_id)
    if not user_data:
        return None

    return UserResponse(
        id=user_data["id"],
        github_username=user_data["github_username"],
        email=user_data["email"],
        avatar_url=user_data.get("avatar_url"),
        role=user_data.get("role", "user"),
    )


def has_permission(user: UserResponse | dict, permission: str) -> bool:
    if permission == "view_logs":
        role = user.role if hasattr(user, "role") else user.get("role", "user")
        return role == "admin"
    return False
