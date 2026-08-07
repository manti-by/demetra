import secrets
from datetime import UTC, datetime, timedelta

import aiohttp
from fastapi import Cookie, HTTPException
from jose import JWTError, jwt
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from demetra.library.exceptions import AuthError
from demetra.library.models import AuthResponse, GitHubUser, TokenData, UserResponse
from demetra.services.allowlist import is_email_allowed, is_github_login_allowed
from demetra.services.database import (
    create_user,
    delete_jwt_token,
    get_jwt_token,
    get_user_by_email,
    get_user_by_github_id,
    get_user_by_id,
    init_db,
    save_jwt_token,
    update_user_password,
)
from demetra.services.passwords import hash_password, verify_password
from demetra.services.tui import print_message
from demetra.settings import GITHUB, JWT


def get_github_auth_url() -> tuple[str, str]:
    """Build the GitHub OAuth authorization URL with a fresh state token.

    Returns:
        tuple[str, str]: The authorization URL and the state value to verify
            the callback against.
    """
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
    """Exchange an OAuth authorization code for a GitHub access token.

    Args:
        code: The authorization code from the GitHub callback.

    Returns:
        str: The GitHub access token.

    Raises:
        AuthError: When OAuth settings are missing or the exchange fails.
    """
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
    """Fetch the authenticated GitHub user profile with an access token.

    Args:
        access_token: A valid GitHub access token.

    Returns:
        GitHubUser: The GitHub user identity.

    Raises:
        AuthError: When the GitHub API request fails.
    """
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
    """Create a signed JWT for a user and its expiry timestamp.

    Args:
        user_id: The user id encoded in the token.

    Returns:
        tuple[str, str]: The JWT and its ISO-8601 expiry timestamp.

    Raises:
        AuthError: When no JWT secret key is configured.
    """
    if not JWT["secret_key"]:
        raise AuthError("JWT_SECRET_KEY must be set")

    expires_delta = timedelta(days=JWT["expiration_days"])
    expire = datetime.now(UTC) + expires_delta

    to_encode = {"user_id": user_id, "exp": int(expire.timestamp())}
    token = jwt.encode(to_encode, JWT["secret_key"], algorithm=JWT["algorithm"])

    return token, expire.isoformat()


async def verify_jwt_token(token: str) -> TokenData | None:
    """Validate a JWT against its signature, stored session and expiry.

    Args:
        token: The JWT to verify.

    Returns:
        TokenData | None: The token payload when valid, otherwise None.
    """
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
    """Return the existing user id for a GitHub user, creating the user on first login.

    Args:
        github_user: The GitHub user identity.

    Returns:
        str: The user id, either newly created or already existing.
    """
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
    """Authenticate a GitHub user, issuing a JWT and storing the session.

    Args:
        github_user: The GitHub user identity.

    Returns:
        AuthResponse: The issued token and the user payload.

    Raises:
        AuthError: When the user record cannot be found after creation, or the
            GitHub account is not on the allowlist.
    """
    if not await is_github_login_allowed(login=github_user.login, email=github_user.email, github_id=github_user.id):
        raise AuthError("GitHub account not authorized")

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
    """Register a new user with an email and password.

    Normalizes the email, validates the password, persists the password hash,
    and returns an authenticated session.

    Args:
        email: The user's email address.
        password: The plaintext password to hash and store.

    Returns:
        AuthResponse: The issued token and the new user payload.

    Raises:
        AuthError: When the email is invalid, already registered, or not
            authorized for registration.
    """
    email = email.strip().lower()

    if not email or "@" not in email:
        raise AuthError("Invalid email address")

    existing = await get_user_by_email(email=email)
    if existing:
        raise AuthError("Email already registered")

    if not await is_email_allowed(email=email):
        raise AuthError("Email not authorized for registration")

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
    """Authenticate a user with email and password credentials.

    Args:
        email: The user's email address.
        password: The plaintext password to verify.

    Returns:
        AuthResponse: The issued token and the user payload.

    Raises:
        AuthError: When the credentials do not match a registered user.
    """
    email = email.strip().lower()

    user_data = await get_user_by_email(email=email)

    if not await is_email_allowed(email=email, user_data=user_data):
        raise AuthError("Invalid email or password")

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
    """Invalidate a JWT by deleting its stored session record.

    Args:
        token: The JWT to revoke.
    """
    await delete_jwt_token(token)


async def get_current_user(token: str) -> UserResponse | None:
    """Resolve a valid token to its authenticated user, if any.

    Args:
        token: The JWT to verify.

    Returns:
        UserResponse | None: The user payload, or None when the token is
            invalid, expired or revoked.
    """
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


async def get_current_user_dep(auth_token: str | None = Cookie(default=None)) -> UserResponse:
    """FastAPI dependency that resolves the authenticated user from the auth cookie."""
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    return user


def has_permission(user: UserResponse | dict, permission: str) -> bool:
    """Check whether a user holds a named permission.

    Args:
        user: The user payload as a UserResponse or a plain mapping.
        permission: The permission name to check.

    Returns:
        bool: True when the user is granted the permission.
    """
    if permission == "view_logs":
        role = user.role if hasattr(user, "role") else user.get("role", "user")
        return role == "admin"
    return False


async def reset_password(email: str, password: str) -> None:
    """Replace the password hash for the user with the given email.

    Args:
        email: The user's email address.
        password: The new plaintext password to hash.

    Raises:
        AuthError: When no user exists for the email.
    """
    email = email.strip().lower()
    password_hash = hash_password(plain=password)

    user_data = await get_user_by_email(email=email)
    if not user_data:
        raise AuthError(f"User with email '{email}' not found")

    await update_user_password(user_id=user_data["id"], password_hash=password_hash)


async def reset_password_cli() -> int:
    """Reset a user's password interactively via the CLI.

    Returns:
        int: The process exit code, 0 on success.
    """
    import getpass

    email = input("Email: ").strip()
    password = getpass.getpass("New password: ")

    try:
        await init_db()
        await reset_password(email=email, password=password)
    except AuthError as e:
        print_message(str(e), style="error")
        return 1
    except SQLAlchemyError as e:
        print_message(f"Database error: {e}", style="error")
        return 1
    else:
        print_message("Password reset successfully", style="success")
        return 0
