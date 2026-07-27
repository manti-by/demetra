import secrets
from datetime import UTC, datetime, timedelta

import aiohttp
from jose import JWTError, jwt
from sqlalchemy.exc import IntegrityError

from demetra.library.exceptions import AuthError
from demetra.library.models import AuthResponse, GitHubUser, TokenData, UserResponse
from demetra.services.database import (
    create_user,
    delete_jwt_token,
    get_jwt_token,
    get_user_by_email,
    get_user_by_github_id,
    get_user_by_id,
    save_jwt_token,
    update_user_password,
)
from demetra.services.passwords import hash_password, verify_password
from demetra.settings import GITHUB, JWT


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
        email=github_user.email or f"gh-{github_user.id}@github.local",
        github_id=github_user.id,
        github_username=github_user.login,
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


async def signup_with_password(email: str, password: str) -> AuthResponse:
    email = email.strip().lower()

    if not email or "@" not in email:
        raise AuthError("Invalid email address")

    existing = await get_user_by_email(email=email)
    if existing:
        raise AuthError("Email already registered")

    password_hash = hash_password(plain=password)

    try:
        user_id = await create_user(
            email=email,
            password_hash=password_hash,
        )
    except IntegrityError as e:
        raise AuthError("Email already registered") from e

    token, expires_at = create_jwt_token(user_id=user_id)
    await save_jwt_token(token=token, user_id=user_id, expires_at=expires_at)

    user_data = await get_user_by_id(user_id=user_id)
    if not user_data:
        raise AuthError("User not found after creation")

    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user_data["id"],
            email=user_data["email"],
        ),
    )


async def login_with_password(email: str, password: str) -> AuthResponse:
    email = email.strip().lower()

    user_data = await get_user_by_email(email=email)
    if not user_data or not user_data.get("password_hash"):
        raise AuthError("Invalid email or password")

    if not verify_password(plain=password, hashed=user_data["password_hash"]):
        raise AuthError("Invalid email or password")

    token, expires_at = create_jwt_token(user_id=user_data["id"])
    await save_jwt_token(token=token, user_id=user_data["id"], expires_at=expires_at)

    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user_data["id"],
            github_username=user_data.get("github_username"),
            email=user_data.get("email"),
            avatar_url=user_data.get("avatar_url"),
            role=user_data.get("role", "user"),
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


async def reset_password(email: str, password: str) -> None:
    email = email.strip().lower()
    password_hash = hash_password(plain=password)

    user_data = await get_user_by_email(email=email)
    if not user_data:
        raise AuthError(f"User with email '{email}' not found")

    await update_user_password(user_id=user_data["id"], password_hash=password_hash)
