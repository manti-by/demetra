"""GitHub OAuth authentication endpoints."""

import json

from fastapi import APIRouter, Cookie, HTTPException, Response
from fastapi.responses import RedirectResponse

from demetra.library.models import UserResponse
from demetra.services.auth import (
    AuthError,
    authenticate_user,
    exchange_code_for_token,
    get_current_user,
    get_github_auth_url,
    get_github_user,
    logout,
)


router = APIRouter()


@router.get("/api/v1/github/login")
async def github_login():
    """Initiate GitHub OAuth login flow.

    Redirects to GitHub's authorization page with appropriate scopes.
    Sets OAuth state cookie for CSRF protection.
    """
    auth_url, state = get_github_auth_url()
    response = RedirectResponse(url=auth_url)
    response.set_cookie(key="oauth_state", value=state, httponly=True, secure=True, samesite="lax")
    return response


@router.get("/api/v1/github/callback")
async def github_callback(
    code: str,
    state: str,
    response: Response,
    oauth_state: str | None = Cookie(default=None),
):
    """Handle GitHub OAuth callback with authorization code.

    Exchanges the authorization code for an access token, retrieves
    user info from GitHub, and creates a session with authentication token.
    Validates OAuth state parameter to prevent CSRF attacks.
    """
    if not oauth_state or oauth_state != state:
        raise HTTPException(status_code=400, detail="Invalid or missing OAuth state")

    response.delete_cookie("oauth_state")

    try:
        access_token = await exchange_code_for_token(code)
        github_user = await get_github_user(access_token)
        auth_response = await authenticate_user(github_user)

        response_data = {
            "token": auth_response.token,
            "user": {
                "id": auth_response.user.id,
                "github_username": auth_response.user.github_username,
                "email": auth_response.user.email,
            },
        }
        response = Response(
            content=json.dumps(response_data),
            media_type="application/json",
        )
        response.set_cookie(
            key="auth_token",
            value=auth_response.token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=14 * 24 * 60 * 60,
        )
        return response
    except AuthError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/v1/github/me", response_model=UserResponse)
async def get_me(auth_token: str | None = Cookie(default=None)):
    """Retrieve the currently authenticated user.

    Requires a valid authentication token in the cookie.
    Returns user profile information including ID, GitHub username, and email.
    """
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    return user


@router.post("/api/v1/github/logout")
async def github_logout(response: Response, auth_token: str | None = Cookie(default=None)):
    """Log out the current user.

    Clears the authentication cookie and invalidates the session.
    Returns a confirmation message.
    """
    if auth_token:
        await logout(auth_token)

    response = Response(content='{"message": "Logged out"}', media_type="application/json")
    response.delete_cookie("auth_token")
    return response
