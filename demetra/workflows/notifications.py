from demetra.library.models import ChatMessageKind, Context
from demetra.services.chat import record_chat_message, record_chat_status
from demetra.services.linear import post_comment, update_ticket_status


async def notify_status(context: Context, state: str) -> bool:
    """Move a task to a Linear state, or record it on a chat session.

    Args:
        context: The workflow context.
        state: The Linear state name, e.g. ``"awaiting_input"``.

    Returns:
        bool: True when the state was applied (chat mode always succeeds for
            step-backed states).

    Raises:
        EnvironmentConfigError: When a Linear state id is not configured.
    """
    if context.is_chat:
        await record_chat_status(task_id=context.linear_task.id, state=state)
        return True

    state_id = context.environment.linear_state(state)
    return await update_ticket_status(task_id=context.linear_task.id, state_id=state_id)


async def notify_message(context: Context, body: str, kind: ChatMessageKind = "message") -> bool:
    """Post a message to Linear, or append it to the chat thread.

    Args:
        context: The workflow context.
        body: The message body.
        kind: The chat message kind (ignored for Linear tasks).

    Returns:
        bool: True when the message was stored.
    """
    if context.is_chat:
        return await record_chat_message(task_id=context.linear_task.id, body=body, kind=kind)
    return await post_comment(task_id=context.linear_task.id, body=body)
