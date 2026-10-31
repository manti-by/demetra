from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam
from redis.exceptions import RedisError

from demetra.library.models import (
    Chat,
    CreateChat,
    CreateChatMessage,
    Session,
    UpdateChat,
    UserResponse,
)
from demetra.services.auth import get_current_user_dep
from demetra.services.persistence.database import (
    create_chat,
    get_chat,
    get_project_by_id,
    get_session,
    get_session_state,
    list_chat_messages,
    list_chats,
    post_chat_message,
    reset_session_for_resume,
    update_chat,
    update_session_step,
)
from demetra.services.persistence.queue import enqueue_workflow


router = APIRouter(prefix="/api/v1/chats")

TASK_ID_PATTERN = r"^CH-\d+$"

VALID_CHAT_STATUSES = {"initial", "awaiting_input", "completed", "failed"}

MAX_TAGS = 20


def _normalize_tags(tags: list[str]) -> list[str]:
    """Normalize chat tags for storage.

    Args:
        tags: The raw tags from the request.

    Returns:
        list[str]: Stripped, de-duplicated tags (case preserved, first
            occurrence wins), capped at :data:`MAX_TAGS`.
    """
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        cleaned = tag.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
        if len(normalized) >= MAX_TAGS:
            break
    return normalized


def _enqueue(project_name: str, task_id: str) -> None:
    """Enqueue a workflow run, surfacing broker failures as HTTP errors.

    Args:
        project_name: The name of the project the task belongs to.
        task_id: The chat task id.

    Raises:
        HTTPException: 503 when the queue broker is unreachable.
    """
    try:
        enqueue_workflow(project_name=project_name, task_id=task_id)
    except (RedisError, OSError, RuntimeError) as e:
        raise HTTPException(status_code=503, detail="Failed to enqueue workflow") from e


@router.get("", response_model=list[Chat])
async def list_chats_endpoint(
    user: UserResponse = Depends(get_current_user_dep),
    tag: str | None = Query(default=None),
) -> list[Chat]:
    """List chat-mode tasks for the authenticated user.

    Args:
        user: The authenticated user.
        tag: Optional tag filter.

    Returns:
        list[Chat]: The user's chats, newest first.
    """
    return await list_chats(user_id=user.id, tag=tag)


@router.post("", response_model=Chat, status_code=201)
async def create_chat_endpoint(
    request: CreateChat,
    user: UserResponse = Depends(get_current_user_dep),
) -> Chat:
    """Create a chat-mode task and start its workflow.

    Creates the chat record and its pending session atomically, then enqueues
    the same workflow the Linear watcher runs.

    Args:
        request: The chat title, description, project and tags.
        user: The authenticated user.

    Returns:
        Chat: The created chat.

    Raises:
        HTTPException: 400 for an empty title or an unready project, 404 when
            the project is not owned, 503 when enqueueing fails.
    """
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")

    project = await get_project_by_id(project_id=request.project_id, user_id=user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("state") != "active" or not project.get("local_path"):
        raise HTTPException(status_code=400, detail="Project is not ready")

    chat = await create_chat(
        user_id=user.id,
        project_id=project["id"],
        title=title,
        description=request.description.strip(),
        tags=_normalize_tags(request.tags),
    )
    _enqueue(project_name=project["name"], task_id=chat.session_task_id)
    return chat


@router.get("/{task_id}", response_model=dict)
async def get_chat_endpoint(
    task_id: Annotated[str, PathParam(pattern=TASK_ID_PATTERN)],
    user: UserResponse = Depends(get_current_user_dep),
) -> dict:
    """Return a chat and its message thread.

    Args:
        task_id: The chat task id.
        user: The authenticated user.

    Returns:
        dict: The chat under ``chat``, its thread under ``messages`` and the
            current pipeline state under ``session``.

    Raises:
        HTTPException: 404 when the chat is absent or not owned.
    """
    chat = await get_chat(task_id=task_id, user_id=user.id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {
        "chat": chat,
        "messages": await list_chat_messages(task_id=task_id),
        "session": await get_session_state(task_id=task_id, user_id=user.id),
    }


@router.patch("/{task_id}", response_model=dict)
async def update_chat_endpoint(
    task_id: Annotated[str, PathParam(pattern=TASK_ID_PATTERN)],
    request: UpdateChat,
    user: UserResponse = Depends(get_current_user_dep),
) -> dict:
    """Update a chat description or session status.

    Only the description is editable content. Setting ``status`` to
    ``initial`` resumes the workflow: the build plan, posted flag and run
    attempts are reset and the task is re-enqueued. Other statuses are
    applied to the session step as-is.

    Args:
        task_id: The chat task id.
        request: The description and/or status to apply.
        user: The authenticated user.

    Returns:
        dict: The updated chat under ``chat``.

    Raises:
        HTTPException: 400 for an unsupported status or an empty update, 404
            when the chat is absent or not owned, 503 when enqueueing fails.
    """
    chat = await get_chat(task_id=task_id, user_id=user.id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    if request.description is None and request.status is None:
        raise HTTPException(status_code=400, detail="Nothing to update")
    if request.status is not None and request.status not in VALID_CHAT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(VALID_CHAT_STATUSES))}",
        )

    updated = chat
    if request.description is not None:
        if (candidate := await update_chat(task_id=task_id, user_id=user.id, description=request.description)) is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        updated = candidate

    if request.status is not None:
        session = await _require_session(task_id=task_id)
        if request.status == "initial":
            await reset_session_for_resume(task_id=task_id)
            project = await get_project_by_id(project_id=session.project_id or chat.project_id, user_id=user.id)
            if project is None:
                raise HTTPException(status_code=404, detail="Project not found")
            _enqueue(project_name=project["name"], task_id=task_id)
        else:
            await update_session_step(task_id=task_id, step=request.status)

    return {"chat": updated}


@router.post("/{task_id}/messages", response_model=dict, status_code=201)
async def create_chat_message_endpoint(
    task_id: Annotated[str, PathParam(pattern=TASK_ID_PATTERN)],
    request: CreateChatMessage,
    user: UserResponse = Depends(get_current_user_dep),
) -> dict:
    """Append a user reply to a chat thread.

    When the session is waiting for input, the reply also resumes the workflow
    so the plan step re-runs with the updated thread as its context.

    Args:
        task_id: The chat task id.
        request: The reply body.
        user: The authenticated user.

    Returns:
        dict: The stored message under ``message`` and whether a workflow run
            was resumed under ``resumed``.

    Raises:
        HTTPException: 400 for an empty body, 404 when the chat is absent or
            not owned, 503 when enqueueing fails.
    """
    chat = await get_chat(task_id=task_id, user_id=user.id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    body = request.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    message = await post_chat_message(task_id=task_id, body=body, author_id=user.id, is_system=False, kind="message")
    if message is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    session = await get_session(task_id=task_id)
    resumed = False
    if session is not None and session.step == "awaiting_input":
        project = await get_project_by_id(project_id=chat.project_id, user_id=user.id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await reset_session_for_resume(task_id=task_id)
        _enqueue(project_name=project["name"], task_id=task_id)
        resumed = True

    return {"message": message, "resumed": resumed}


async def _require_session(task_id: str) -> Session:
    """Load a session or raise a 404.

    Args:
        task_id: The chat task id.

    Returns:
        Session: The session record.

    Raises:
        HTTPException: 404 when the session does not exist.
    """
    session = await get_session(task_id=task_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
