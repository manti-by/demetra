import asyncio
import logging
import os
import re
from typing import Annotated

import aiofiles
from fastapi import APIRouter, Cookie, Query, WebSocket, WebSocketDisconnect

from demetra.services.auth import get_current_user
from demetra.settings import DEBUG, LOG_DIR


UUID_PATTERN = re.compile(r"^[a-f0-9-]{36}$", re.IGNORECASE)

router = APIRouter(prefix="/ws/v1/watcher")


@router.websocket("/logs")
async def watcher_logs(
    websocket: WebSocket,
    auth_token: str | None = Cookie(default=None),
    task_id: Annotated[str | None, Query()] = None,
    token: Annotated[str | None, Query()] = None,
) -> None:
    """Stream log files via WebSocket in real-time.

    Authenticates the user and validates the task_id as a UUID.
    Sends the last 10 lines immediately, then continuously streams
    new log content as it's written. Includes path traversal protection.
    """
    if DEBUG and not auth_token:
        auth_token = token

    if not auth_token:
        await websocket.close(code=4001, reason="Not authenticated")
        return

    if not await get_current_user(token=auth_token):
        await websocket.close(code=4003, reason="Forbidden")
        return

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

    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    await websocket.accept()

    try:
        async with aiofiles.open(resolved_path) as f:
            content = await f.read()
            lines = content.strip().split("\n")
            last_100_lines = lines[-100:] if len(lines) > 100 else lines
            for line in last_100_lines:
                if line:
                    await websocket.send_text(line)

        async with aiofiles.open(resolved_path) as f:
            await f.seek(0, os.SEEK_END)
            current_position = await f.tell()

            while True:
                await asyncio.sleep(0.5)

                async with aiofiles.open(resolved_path) as file:
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
