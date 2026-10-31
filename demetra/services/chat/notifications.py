from demetra.library.models import ChatMessageKind
from demetra.services.persistence.database import (
    get_chat_by_task_id,
    post_chat_message,
    update_session_step,
)


STATUS_STEPS = {"awaiting_input", "initial", "completed", "failed", "researched"}


async def is_chat_task(task_id: str) -> bool:
    """Return whether a task id is backed by a chat record.

    Args:
        task_id: The task id to check.

    Returns:
        bool: True when a ``chats`` row exists for the task.
    """
    return await get_chat_by_task_id(task_id=task_id) is not None


async def record_chat_status(task_id: str, state: str) -> None:
    """Record a workflow status on the chat session instead of Linear.

    Only real session steps are written; Linear-only states such as
    ``in_progress`` are no-ops because the session step already drives the UI.

    Args:
        task_id: The chat task id.
        state: The Linear-style state name used by the call site.
    """
    if state in STATUS_STEPS:
        await update_session_step(task_id=task_id, step=state)


async def record_chat_message(task_id: str, body: str, kind: ChatMessageKind = "message") -> bool:
    """Append a workflow-produced message to the chat thread.

    Args:
        task_id: The chat task id.
        body: The message body.
        kind: The message kind.

    Returns:
        bool: True when the message was stored.
    """
    return await post_chat_message(task_id=task_id, body=body, is_system=True, kind=kind) is not None
