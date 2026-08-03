import asyncio
import logging
import os
import re
from typing import Annotated

import aiofiles
from fastapi import APIRouter, Cookie, Query, WebSocket, WebSocketDisconnect

from demetra.services.auth import get_current_user
from demetra.services.database import get_session_id_by_task_id, get_session_step_name
from demetra.settings import DEBUG, LOG_DIR


UUID_PATTERN = re.compile(r"^[a-f0-9-]{36}$", re.IGNORECASE)

router = APIRouter(prefix="/ws/v1/watcher")


async def send_log(websocket: WebSocket, line: str) -> None:
    await websocket.send_json({"type": "log", "data": {"text": line}})


async def send_status(websocket: WebSocket, step: str, name: str = "") -> None:
    await websocket.send_json({"type": "status", "data": {"step": step, "name": name}})


async def send_deleted(websocket: WebSocket) -> None:
    await websocket.send_json({"type": "status", "data": {"step": "deleted", "name": ""}})


async def reject_connection(websocket: WebSocket, *, code: int, reason: str) -> None:
    """Accept the connection before closing so the application close code reaches the client.

    Closing before accepting only fails the HTTP handshake, and servers like uvicorn
    deliver an HTTP 403 instead of the requested close code (e.g. 4001, 4003, 4000, 4004).
    """
    try:
        await websocket.accept()
        await websocket.close(code=code, reason=reason)
    except RuntimeError:
        pass


@router.websocket("/logs")
async def watcher_logs(
    websocket: WebSocket,
    auth_token: str | None = Cookie(default=None),
    task_id: Annotated[str | None, Query()] = None,
    token: Annotated[str | None, Query()] = None,
) -> None:
    """Stream log files and session status via WebSocket in real-time.

    Authenticates the user and validates the task_id as a UUID.
    Sends JSON envelopes with type "log" (data.text) for log lines
    and "status" (data.step, data.name) for session step changes.
    Includes path traversal protection.
    """
    if DEBUG and not auth_token:
        auth_token = token

    if not auth_token:
        await reject_connection(websocket=websocket, code=4001, reason="Not authenticated")
        return

    user = await get_current_user(token=auth_token)
    if not user:
        await reject_connection(websocket=websocket, code=4003, reason="Forbidden")
        return

    if not task_id or not UUID_PATTERN.match(task_id):
        await reject_connection(websocket=websocket, code=4000, reason="Invalid or missing task_id")
        return

    if not await get_session_id_by_task_id(task_id=task_id, user_id=user.id):
        await reject_connection(websocket=websocket, code=4004, reason="Session not found")
        return

    log_path = LOG_DIR / f"sessions/{task_id}.log"
    if LOG_DIR.name == "sessions":
        log_path = LOG_DIR / f"{task_id}.log"

    try:
        resolved_path = log_path.resolve()
        log_dir_resolved = LOG_DIR.resolve()
    except OSError:
        await reject_connection(websocket=websocket, code=4000, reason="Invalid log path")
        return

    if not resolved_path.is_relative_to(log_dir_resolved):
        await reject_connection(websocket=websocket, code=4000, reason="Invalid log path")
        return

    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    await websocket.accept()

    last_seen_step: str | None = None
    last_seen_name: str = ""

    try:
        status_info = await get_session_step_name(task_id=task_id, user_id=user.id)
        if status_info is not None:
            last_seen_step, last_seen_name = status_info
            await send_status(websocket=websocket, step=last_seen_step, name=last_seen_name)
        else:
            await send_deleted(websocket=websocket)
            await websocket.close(code=4004, reason="Session not found")
            return

        try:
            async with aiofiles.open(resolved_path) as f:
                content = await f.read()
                lines = content.splitlines()
                last_100_lines = lines[-100:] if len(lines) > 100 else lines
                for line in last_100_lines:
                    await send_log(websocket=websocket, line=line)
        except FileNotFoundError:
            pass

        async with aiofiles.open(resolved_path, mode="a+") as f:
            await f.seek(0, os.SEEK_END)
            current_position = await f.tell()

            status_ticks = 0
            while True:
                await asyncio.sleep(0.5)
                status_ticks += 1

                async with aiofiles.open(resolved_path, mode="a+") as file:
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
                            await send_log(websocket=websocket, line=line)

                if status_ticks >= 2:
                    status_ticks = 0
                    status_info = await get_session_step_name(task_id=task_id, user_id=user.id)
                    if status_info is None:
                        await send_deleted(websocket=websocket)
                        break
                    step, name = status_info
                    if step != last_seen_step or name != last_seen_name:
                        last_seen_step = step
                        last_seen_name = name
                        await send_status(websocket=websocket, step=step, name=name)

    except WebSocketDisconnect:
        pass

    except OSError as e:
        logging.exception("Error streaming logs: %s", e)
        await websocket.close(code=4002, reason="Stream error")
        return
