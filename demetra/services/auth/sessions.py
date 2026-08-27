from fastapi import Cookie, HTTPException

import demetra.services.auth as service
from demetra.library.exceptions import AuthError, GitHubAccountNotAuthorizedError, RegistrationNotAllowedError
from demetra.library.models import AuthResponse, GitHubUser, UserResponse


# Fixed bcrypt hash compared against when no user exists, so an unknown email
# costs the same bcrypt work as a known one and cannot be told apart by timing.
_DUMMY_PASSWORD_HASH = "$2b$12$jxVmuPVagAbjwXvjcTobOu2CkCK4ZBowPWm4Wqy90Umtkzr4dSAbe"  # noqa: S105


async def get_or_create_user(github_user: GitHubUser) -> str:
    """Return the existing user id for a GitHub user, creating the user on first login.

    Args:
        github_user: The GitHub user identity.

    Returns:
        str: The user id, either newly created or already existing.
    """
    existing_user = await service.get_user_by_github_id(github_user.id)
    if existing_user:
        return existing_user["id"]

    return await service.create_user(
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
    if not await service.is_github_login_allowed(
        login=github_user.login, email=github_user.email, github_id=github_user.id
    ):
        raise GitHubAccountNotAuthorizedError("GitHub account not authorized")

    user_id = await get_or_create_user(github_user)
    token, expires_at = service.create_jwt_token(user_id)

    await service.save_jwt_token(token=token, user_id=user_id, expires_at=expires_at)

    user_data = await service.get_user_by_id(user_id)
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
    from sqlalchemy.exc import IntegrityError

    email = email.strip().lower()

    if not email or "@" not in email:
        raise AuthError("Invalid email address")

    existing = await service.get_user_by_email(email=email)
    if existing:
        raise AuthError("Email already registered")

    if not await service.is_email_allowed(email=email):
        raise RegistrationNotAllowedError("Email not authorized for registration")

    password_hash = service.hash_password(plain=password)

    try:
        user_id = await service.create_user(
            email=email,
            password_hash=password_hash,
        )
    except IntegrityError as e:
        raise AuthError("Email already registered") from e

    token, expires_at = service.create_jwt_token(user_id=user_id)
    await service.save_jwt_token(token=token, user_id=user_id, expires_at=expires_at)

    user_data = await service.get_user_by_id(user_id=user_id)
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

    user_data = await service.get_user_by_email(email=email)

    if user_data and user_data.get("password_hash"):
        password_valid = service.verify_password(plain=password, hashed=user_data["password_hash"])
    else:
        # Equalize timing: an unknown email still pays for one bcrypt compare
        # against a fixed dummy hash before the generic error is raised.
        service.verify_password(plain=password, hashed=_DUMMY_PASSWORD_HASH)
        password_valid = False

    if not password_valid or user_data is None:
        raise AuthError("Invalid email or password")

    if not await service.is_email_allowed(email=email, user_data=user_data):
        raise AuthError("Invalid email or password")

    token, expires_at = service.create_jwt_token(user_id=user_data["id"])
    await service.save_jwt_token(token=token, user_id=user_data["id"], expires_at=expires_at)

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
    await service.delete_jwt_token(token)


async def get_current_user(token: str) -> UserResponse | None:
    """Resolve a valid token to its authenticated user, if any.

    Args:
        token: The JWT to verify.

    Returns:
        UserResponse | None: The user payload, or None when the token is
            invalid, expired or revoked.
    """
    token_data = await service.verify_jwt_token(token)
    if not token_data:
        return None

    user_data = await service.get_user_by_id(token_data.user_id)
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

    if not (user := await service.get_current_user(token=auth_token)):
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
    """Replace the password hash for the user with the given email, revoking
    every stored JWT session for that user in the same transaction.

    The password update bumps the user's ``password_version``, so any session
    minted concurrently after the token snapshot is rejected by
    :func:`verify_jwt_token` once the reset commits.

    Args:
        email: The user's email address.
        password: The new plaintext password to hash.

    Raises:
        AuthError: When no user exists for the email.
    """
    email = email.strip().lower()
    password_hash = service.hash_password(plain=password)

    user_data = await service.get_user_by_email(email=email)
    if not user_data:
        raise AuthError(f"User with email '{email}' not found")

    user_id = user_data["id"]
    tokens = await service.get_user_jwt_tokens(user_id=user_id)
    async with service.get_transaction() as connection:
        for token_data in tokens:
            await service.delete_jwt_token(token=token_data["token"], connection=connection)
        await service.update_user_password(user_id=user_id, password_hash=password_hash, connection=connection)


async def reset_password_cli() -> int:
    """Reset a user's password interactively via the CLI.

    Returns:
        int: The process exit code, 0 on success.
    """
    import getpass

    from sqlalchemy.exc import SQLAlchemyError

    from demetra.services.runtime.tui import print_message

    email = input("Email: ").strip()
    password = getpass.getpass("New password: ")

    try:
        await service.init_db()
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
