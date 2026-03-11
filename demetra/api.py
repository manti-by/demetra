import asyncio
import json
import logging
import os
import re
from typing import Annotated

import aiofiles
from fastapi import Cookie, FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse

from demetra.library.models import TicketRequest, TicketResponse, UserKeysUpdateRequest, UserResponse
from demetra.services.auth import (
    AuthError,
    authenticate_user,
    exchange_code_for_token,
    get_current_user,
    get_github_auth_url,
    get_github_user,
    has_permission,
    logout,
)
from demetra.services.database import get_sessions, update_user_keys
from demetra.services.groq import process_text_with_groq
from demetra.services.linear import create_linear_ticket
from demetra.services.utils import get_project_id_by_name
from demetra.settings import LINEAR, LOG_DIR


UUID_PATTERN = re.compile(r"^[a-f0-9-]{36}$", re.IGNORECASE)


app = FastAPI(title="Demetra API")


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


@app.patch("/api/v1/users/me/keys")
async def update_user_keys_endpoint(
    request: UserKeysUpdateRequest,
    auth_token: str | None = Cookie(default=None),
):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await get_current_user(auth_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    await update_user_keys(user.id, request.keys)

    return {"message": "Keys updated successfully"}


@app.post("/api/v1/github/logout")
async def github_logout(response: Response, auth_token: str | None = Cookie(default=None)):
    if auth_token:
        await logout(auth_token)

    response = Response(content='{"message": "Logged out"}', media_type="application/json")
    response.delete_cookie("auth_token")
    return response


@app.post("/api/v1/tickets", response_model=TicketResponse)
async def create_ticket(request: TicketRequest, auth_token: str | None = Cookie(default=None)):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

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


@app.get("/api/v1/sessions")
async def list_sessions(
    auth_token: str | None = Cookie(default=None),
    status: Annotated[str | None, Query()] = None,
) -> list[dict]:
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await get_current_user(auth_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if status and status not in ("pending", "processed", "failed"):
        raise HTTPException(status_code=400, detail="Invalid status. Must be one of: pending, processed, failed")

    sessions = await get_sessions(status)
    return sessions


@app.websocket("/ws/v1/watcher/logs")
async def watcher_logs(
    websocket: WebSocket,
    auth_token: str | None = Cookie(default=None),
    task_id: Annotated[str | None, Query()] = None,
) -> None:
    if not auth_token:
        await websocket.close(code=4001, reason="Not authenticated")
        return

    user = await get_current_user(auth_token)
    if not user:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    if not has_permission(user, "view_logs"):
        await websocket.close(code=4003, reason="Forbidden: insufficient permissions")
        return

    if not task_id or not UUID_PATTERN.match(task_id):
        await websocket.close(code=4000, reason="Invalid or missing task_id")
        return

    log_path = LOG_DIR / f"sessions/{task_id}.log"
    if LOG_DIR.name == "sessions":
        log_path = LOG_DIR / f"{task_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    await websocket.accept()

    try:
        async with aiofiles.open(log_path) as f:
            content = await f.read()
            lines = content.strip().split("\n")
            last_10_lines = lines[-10:] if len(lines) > 10 else lines
            for line in last_10_lines:
                if line:
                    await websocket.send_text(line)

        async with aiofiles.open(log_path) as f:
            await f.seek(0, os.SEEK_END)
            current_position = await f.tell()

            while True:
                await asyncio.sleep(0.5)

                async with aiofiles.open(log_path) as file:
                    await file.seek(0, os.SEEK_END)
                    file_size = await file.tell()

                    if current_position > file_size:
                        current_position = file_size

                    await file.seek(current_position)
                    new_content = await file.read()
                    current_position = await file.tell()

                if new_content:
                    lines = new_content.strip().split("\n")
                    for line in lines:
                        if line:
                            await websocket.send_text(line)
    except WebSocketDisconnect:
        pass
    except OSError as e:
        logging.exception("Error streaming logs: %s", e)
        await websocket.close(code=4002, reason=f"Stream error: {e}")
        return
