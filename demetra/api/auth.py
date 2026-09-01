import json

from fastapi import APIRouter, Cookie, HTTPException, Response

from demetra.library.exceptions import AuthError, RegistrationNotAllowedError, WaitlistedError
from demetra.library.models import LoginRequest, SignupRequest, WaitlistedResponse
from demetra.services.auth import login_with_password, logout, signup_with_password
from demetra.settings import COOKIE_SAMESITE, COOKIE_SECURE


router = APIRouter(prefix="/api/v1/auth")


def _auth_response(auth_response):
    """Build the JSON response body describing the authenticated user.

    Args:
        auth_response: An AuthResponse instance with the user payload.

    Returns:
        Response: A JSON response containing only the public user fields.
    """
    return Response(
        content=json.dumps(
            {
                "user": {
                    "id": auth_response.user.id,
                    "github_username": auth_response.user.github_username,
                    "email": auth_response.user.email,
                    "avatar_url": auth_response.user.avatar_url,
                    "role": auth_response.user.role,
                },
            }
        ),
        media_type="application/json",
    )


def _set_auth_cookie(*, response: Response, token: str) -> Response:
    """Set the httpOnly authentication cookie on a response.

    Args:
        response: The response to attach the cookie to.
        token: The JWT to store in the cookie.

    Returns:
        Response: The same response with the auth cookie set.
    """
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=14 * 24 * 60 * 60,
    )
    return response


@router.post("/signup")
async def signup(request: SignupRequest) -> Response:
    """Register a new user with email and password.

    Args:
        request: The signup payload with email and password.

    Returns:
        Response: A JSON user payload with an auth cookie set.

    Raises:
        HTTPException: 400 when the credentials are invalid.
    """
    try:
        auth_response = await signup_with_password(email=request.email, password=request.password)
    except WaitlistedError as e:
        waitlisted = WaitlistedResponse(entry_id=e.entry_id)
        return Response(
            content=json.dumps({"status": waitlisted.status, "message": waitlisted.message}),
            media_type="application/json",
            status_code=202,
        )
    except AuthError as e:
        status_code = 403 if isinstance(e, RegistrationNotAllowedError) else 400
        raise HTTPException(status_code=status_code, detail=str(e)) from e

    return _set_auth_cookie(
        response=_auth_response(auth_response=auth_response),
        token=auth_response.token,
    )


@router.post("/login")
async def login(request: LoginRequest) -> Response:
    """Authenticate an existing user and set an auth cookie.

    Args:
        request: The login payload with email and password.

    Returns:
        Response: A JSON user payload with an auth cookie set.

    Raises:
        HTTPException: 401 when the credentials are invalid.
    """
    try:
        auth_response = await login_with_password(email=request.email, password=request.password)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    return _set_auth_cookie(
        response=_auth_response(auth_response=auth_response),
        token=auth_response.token,
    )


@router.post("/logout")
async def do_logout(response: Response, auth_token: str | None = Cookie(default=None)) -> Response:
    """Invalidate the session token and clear the auth cookie.

    Args:
        response: The response to clear the cookie on.
        auth_token: The current auth cookie value, if any.

    Returns:
        Response: A confirmation response with the auth cookie deleted.
    """
    if auth_token:
        await logout(token=auth_token)

    response = Response(content='{"message": "Logged out"}', media_type="application/json")
    response.delete_cookie("auth_token")
    return response
