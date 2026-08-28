import json

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse

from demetra.library.exceptions import AuthError, GitHubAccountNotAuthorizedError, WaitlistedError
from demetra.library.models import UserResponse, WaitlistedResponse
from demetra.services.auth import (
    authenticate_user,
    exchange_code_for_token,
    get_current_user_dep,
    get_github_auth_url,
    get_github_user,
    logout,
)
from demetra.settings import COOKIE_SAMESITE, COOKIE_SECURE


router = APIRouter(prefix="/api/v1/github")


@router.get("/login")
async def github_login():
    """Initiate GitHub OAuth login flow.

    Redirects to GitHub's authorization page with appropriate scopes.
    Sets OAuth state cookie for CSRF protection.
    """
    auth_url, state = get_github_auth_url()
    response = RedirectResponse(url=auth_url)
    response.set_cookie(key="oauth_state", value=state, httponly=True, secure=COOKIE_SECURE, samesite="lax")
    return response


@router.get("/callback")
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
                "avatar_url": auth_response.user.avatar_url,
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
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            max_age=14 * 24 * 60 * 60,
        )
        return response
    except WaitlistedError as e:
        waitlisted = WaitlistedResponse(entry_id=e.entry_id)
        return Response(
            content=json.dumps({"status": waitlisted.status, "message": waitlisted.message}),
            media_type="application/json",
            status_code=202,
        )
    except AuthError as e:
        status_code = 403 if isinstance(e, GitHubAccountNotAuthorizedError) else 400
        raise HTTPException(status_code=status_code, detail=str(e)) from e


@router.get("/me", response_model=UserResponse)
async def get_me(user: UserResponse = Depends(get_current_user_dep)):
    """Retrieve the currently authenticated user.

    Requires a valid authentication token in the cookie.
    Returns user profile information including ID, GitHub username, and email.
    """
    return user


@router.post("/logout")
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
