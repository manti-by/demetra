import json

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from demetra.api.responses import client_host, delete_cookie_header, waitlisted_response
from demetra.library.exceptions import AuthError, WaitlistedError
from demetra.library.models import UserResponse
from demetra.services.auth import (
    authenticate_user,
    exchange_code_for_token,
    get_current_user_dep,
    get_github_auth_url,
    get_github_user,
    logout,
)
from demetra.services.utils import auth_rate_limiter
from demetra.settings import AUTH_COOKIE_NAME, COOKIE_SAMESITE, COOKIE_SECURE, OAUTH_STATE_COOKIE


router = APIRouter(prefix="/api/v1/github")


@router.get("/login")
async def github_login():
    """Initiate GitHub OAuth login flow.

    Redirects to GitHub's authorization page with appropriate scopes.
    Sets OAuth state cookie for CSRF protection.
    """
    auth_url, state = get_github_auth_url()
    response = RedirectResponse(url=auth_url)
    response.set_cookie(key=OAUTH_STATE_COOKIE, value=state, httponly=True, secure=COOKIE_SECURE, samesite="lax")
    return response


@router.get("/callback")
async def github_callback(
    code: str,
    state: str,
    http_request: Request,
    response: Response,
    oauth_state: str | None = Cookie(default=None),
):
    """Handle GitHub OAuth callback with authorization code.

    Exchanges the authorization code for an access token, retrieves
    user info from GitHub, and creates a session with authentication token.
    Validates OAuth state parameter to prevent CSRF attacks. Rate limits
    the endpoint per client IP to bound unauthenticated waitlist writes.
    """
    if not auth_rate_limiter.is_allowed(key=client_host(http_request)):
        raise HTTPException(status_code=429, detail="Too many requests, try again later")

    if not oauth_state or oauth_state != state:
        raise HTTPException(status_code=400, detail="Invalid or missing OAuth state")

    response.delete_cookie(OAUTH_STATE_COOKIE)

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
        success_response = Response(
            content=json.dumps(response_data),
            media_type="application/json",
        )
        success_response.delete_cookie(OAUTH_STATE_COOKIE)
        success_response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=auth_response.token,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            max_age=14 * 24 * 60 * 60,
        )
        return success_response
    except WaitlistedError as e:
        wl_response = waitlisted_response(entry_id=e.entry_id)
        wl_response.delete_cookie(OAUTH_STATE_COOKIE)
        return wl_response
    except AuthError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
            headers=delete_cookie_header(name=OAUTH_STATE_COOKIE),
        ) from e


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
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response
