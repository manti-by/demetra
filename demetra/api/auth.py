import json

from fastapi import APIRouter, Cookie, HTTPException, Response

from demetra.library.exceptions import AuthError
from demetra.library.models import LoginRequest, SignupRequest
from demetra.services.auth import login_with_password, logout, signup_with_password


router = APIRouter(prefix="/api/v1/auth")


def _auth_response(auth_response):
    return Response(
        content=json.dumps(
            {
                "token": auth_response.token,
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


def _set_auth_cookie(response, token):
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=14 * 24 * 60 * 60,
    )
    return response


@router.post("/signup")
async def signup(request: SignupRequest):
    """Register a new account with email and password.

    Creates a user, issues a JWT, and sets the auth_token cookie.
    The resulting session works with all existing authenticated endpoints.
    """
    try:
        auth_response = await signup_with_password(email=request.email, password=request.password)
    except AuthError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return _set_auth_cookie(_auth_response(auth_response), auth_response.token)


@router.post("/login")
async def login(request: LoginRequest):
    """Authenticate with email and password.

    Validates credentials, issues a JWT, and sets the auth_token cookie.
    """
    try:
        auth_response = await login_with_password(email=request.email, password=request.password)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    return _set_auth_cookie(_auth_response(auth_response), auth_response.token)


@router.post("/logout")
async def do_logout(response: Response, auth_token: str | None = Cookie(default=None)):
    """Log out the current user.

    Invalidates the session and clears the auth_token cookie.
    """
    if auth_token:
        await logout(auth_token)

    response = Response(content='{"message": "Logged out"}', media_type="application/json")
    response.delete_cookie("auth_token")
    return response
