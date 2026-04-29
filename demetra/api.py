import asyncio
import json
import logging
import os
import re
from typing import Annotated

import aiofiles
from fastapi import Cookie, FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse

from demetra.library.models import (
    CreateProject,
    CreateTicket,
    Project,
    Ticket,
    UpdateProject,
    UserKeysUpdateRequest,
    UserResponse,
)
from demetra.services.auth import (
    AuthError,
    authenticate_user,
    exchange_code_for_token,
    get_current_user,
    get_github_auth_url,
    get_github_user,
    logout,
)
from demetra.services.database import (
    create_project,
    delete_project,
    get_project_by_id,
    get_projects_by_user,
    get_sessions,
    update_project,
    update_user_keys,
)
from demetra.services.groq import process_text_with_groq
from demetra.services.linear import create_linear_ticket
from demetra.services.project import cleanup_project_resources, parse_github_url, setup_project
from demetra.services.utils import get_project_id_by_name
from demetra.settings import LINEAR, LOG_DIR


UUID_PATTERN = re.compile(r"^[a-f0-9-]{36}$", re.IGNORECASE)


app = FastAPI(title="Demetra API")


@app.get("/api/v1/github/login")
async def github_login():
    auth_url, state = get_github_auth_url()
    response = RedirectResponse(url=auth_url)
    response.set_cookie(key="oauth_state", value=state, httponly=True, secure=True, samesite="lax")
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


@app.get("/api/v1/github/me", response_model=UserResponse)
async def get_me(auth_token: str | None = Cookie(default=None)):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    return user


@app.patch("/api/v1/users/me/keys")
async def update_user_keys_endpoint(
    request: UserKeysUpdateRequest,
    auth_token: str | None = Cookie(default=None),
):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    await update_user_keys(user_id=user.id, keys=request.keys)
    return {"message": "Keys updated successfully"}


@app.post("/api/v1/github/logout")
async def github_logout(response: Response, auth_token: str | None = Cookie(default=None)):
    if auth_token:
        await logout(auth_token)

    response = Response(content='{"message": "Logged out"}', media_type="application/json")
    response.delete_cookie("auth_token")
    return response


@app.post("/api/v1/tickets", response_model=Ticket)
async def create_ticket(request: CreateTicket, auth_token: str | None = Cookie(default=None)):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not await get_current_user(token=auth_token):
        raise HTTPException(status_code=401, detail="Invalid token")

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

    return Ticket(**ticket)


@app.get("/api/v1/sessions")
async def list_sessions(
    auth_token: str | None = Cookie(default=None),
    status: Annotated[str | None, Query()] = None,
) -> list[dict]:
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    if status and status not in ("pending", "processed", "failed"):
        raise HTTPException(status_code=400, detail="Invalid status. Must be one of: pending, processed, failed")

    sessions = await get_sessions(user_id=user.id, status=status)
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

    if not await get_current_user(token=auth_token):
        await websocket.close(code=4003, reason="Forbidden")

    if not task_id or not UUID_PATTERN.match(task_id):
        await websocket.close(code=4000, reason="Invalid or missing task_id")
        return

    log_path = LOG_DIR / f"sessions/{task_id}.log"
    if LOG_DIR.name == "sessions":
        log_path = LOG_DIR / f"{task_id}.log"

    try:
        resolved_path = log_path.resolve()
        log_dir_resolved = LOG_DIR.resolve()
    except OSError:
        await websocket.close(code=4000, reason="Invalid log path")
        return

    if not resolved_path.is_relative_to(log_dir_resolved):
        await websocket.close(code=4000, reason="Invalid log path")
        return

    log_path.parent.mkdir(parents=True, exist_ok=True)

    await websocket.accept()

    try:
        async with aiofiles.open(log_path) as f:
            content = await f.read()
            lines = content.strip().split("\n")
            last_50_lines = lines[-50:] if len(lines) > 50 else lines
            for line in last_50_lines:
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


@app.get("/api/v1/projects", response_model=list[Project])
async def list_projects(auth_token: str | None = Cookie(default=None)):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    projects = await get_projects_by_user(user_id=user.id)
    return [
        Project(
            id=p["id"],
            user_id=p.get("user_id"),
            linear_project_id=p.get("linear_project_id"),
            name=p["name"],
            state=p["state"],
            repository_url=p["repository_url"],
            repository_name=p["repository_name"],
            repository_owner=p["repository_owner"],
            local_path=p["local_path"],
            created_at=p["created_at"].isoformat() if p.get("created_at") else "",
            updated_at=p["updated_at"].isoformat() if p.get("updated_at") else "",
        )
        for p in projects
    ]


@app.post("/api/v1/projects", response_model=Project)
async def create_project_endpoint(
    request: CreateProject,
    auth_token: str | None = Cookie(default=None),
):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    if not (project_name := request.name.strip()):
        raise HTTPException(status_code=400, detail="Project name cannot be empty")

    if not (repository_url := request.repository_url.strip()):
        raise HTTPException(status_code=400, detail="Repository URL cannot be empty")

    if not (parsed_repository_url := parse_github_url(repository_url)):
        raise HTTPException(status_code=400, detail=f"Invalid GitHub repository URL: {repository_url}")

    repository_owner, repository_name = parsed_repository_url
    project = await create_project(
        user_id=user.id,
        name=project_name,
        repository_url=repository_url,
        repository_name=repository_name,
        repository_owner=repository_owner,
        linear_project_id=request.linear_project_id,
        state="provisioning",
    )

    project_id, linear_project_id = project["id"], request.linear_project_id
    try:
        setup_info = await setup_project(project=project)
        local_path = setup_info["local_path"]

    except ValueError as e:
        logging.error(f"Failed to setup project: {e}")
        await cleanup_project_resources(project=project)
        await update_project(project_id=project_id, user_id=user.id, state="failed")
        raise HTTPException(status_code=400, detail="Invalid project name or repository URL") from e

    except Exception as e:
        logging.exception(f"Failed to setup project: {e}")
        await cleanup_project_resources(project=project)
        await update_project(project_id=project_id, user_id=user.id, state="failed")
        raise HTTPException(status_code=500, detail="Internal server error") from e

    if not (
        updated_project := await update_project(
            project_id=project_id, user_id=user.id, local_path=local_path, state="active"
        )
    ):
        raise HTTPException(status_code=500, detail="Failed to update project state")

    return Project(
        id=project_id,
        user_id=user.id,
        name=project_name,
        state=updated_project["state"],
        repository_url=repository_url,
        repository_name=repository_name,
        repository_owner=repository_owner,
        linear_project_id=linear_project_id,
        local_path=local_path,
        created_at=updated_project["created_at"],
        updated_at=updated_project["updated_at"],
    )


@app.get("/api/v1/projects/{project_id}", response_model=Project)
async def get_project_endpoint(
    project_id: str,
    auth_token: str | None = Cookie(default=None),
):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not (project := await get_project_by_id(project_id=project_id, user_id=user.id)):
        raise HTTPException(status_code=404, detail="Project not found")

    return Project(
        id=project["id"],
        user_id=project.get("user_id"),
        linear_project_id=project.get("linear_project_id"),
        name=project["name"],
        state=project["state"],
        repository_url=project["repository_url"],
        repository_name=project["repository_name"],
        repository_owner=project["repository_owner"],
        local_path=project["local_path"],
        created_at=project["created_at"].isoformat() if project.get("created_at") else "",
        updated_at=project["updated_at"].isoformat() if project.get("updated_at") else "",
    )


@app.patch("/api/v1/projects/{project_id}", response_model=Project)
async def update_project_endpoint(
    project_id: str,
    request: UpdateProject,
    auth_token: str | None = Cookie(default=None),
):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    project = await update_project(
        project_id=project_id,
        user_id=user.id,
        name=request.name.strip() if request.name else None,
        repository_url=request.repository_url.strip() if request.repository_url else None,
        linear_project_id=request.linear_project_id,
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return Project(
        id=project["id"],
        user_id=project["user_id"],
        linear_project_id=project.get("linear_project_id"),
        name=project["name"],
        state=project["state"],
        repository_url=project["repository_url"],
        repository_name=project["repository_name"],
        repository_owner=project["repository_owner"],
        local_path=project["local_path"],
        created_at=project["created_at"].isoformat() if project.get("created_at") else "",
        updated_at=project["updated_at"].isoformat() if project.get("updated_at") else "",
    )


@app.delete("/api/v1/projects/{project_id}")
async def delete_project_endpoint(
    project_id: str,
    auth_token: str | None = Cookie(default=None),
):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    await delete_project(project_id=project_id, user_id=user.id)
    return {"message": "Project deleted successfully"}
