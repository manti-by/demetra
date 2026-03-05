import json

from fastapi import Cookie, FastAPI, HTTPException, Response
from fastapi.responses import RedirectResponse

from demetra.library.models import TicketRequest, TicketResponse, UserResponse
from demetra.services.auth import (
    AuthError,
    authenticate_user,
    exchange_code_for_token,
    get_current_user,
    get_github_auth_url,
    get_github_user,
    logout,
)
from demetra.services.groq import process_text_with_groq
from demetra.services.linear import create_linear_ticket
from demetra.services.utils import get_project_id_by_name
from demetra.settings import LINEAR


app = FastAPI(title="Demetra Ticket API")


@app.get("/api/v1/github/login")
async def github_login():
    auth_url, state = get_github_auth_url()
    response = RedirectResponse(url=auth_url)
    response.set_cookie("oauth_state", state, httponly=True, secure=True, samesite="lax")
    return response


@app.get("/api/v1/github/callback")
async def github_callback(code: str, response: Response):
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
            "auth_token", auth_response.token, httponly=True, secure=True, samesite="lax", max_age=14 * 24 * 60 * 60
        )
        return response
    except AuthError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/v1/github/me", response_model=UserResponse)
async def get_me(auth_token: str | None = Cookie(default=None)):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await get_current_user(auth_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user


@app.post("/api/v1/github/logout")
async def github_logout(response: Response, auth_token: str | None = Cookie(default=None)):
    if auth_token:
        await logout(auth_token)

    response = Response(content='{"message": "Logged out"}', media_type="application/json")
    response.delete_cookie("auth_token")
    return response


@app.post("/api/v1/tickets/", response_model=TicketResponse)
async def create_ticket(request: TicketRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        processed = await process_text_with_groq(request.text)

        project_name = processed["project_name"]
        project_id = await get_project_id_by_name(project_name) or LINEAR["default_project"]

        ticket = await create_linear_ticket(
            title=processed["title"],
            description=processed["description"],
            technical_requirements=processed["technical_requirements"],
            acceptance_criteria=processed["acceptance_criteria"],
            project_id=project_id,
        )
    except (TypeError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return TicketResponse(**ticket)
