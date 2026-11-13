from demetra.library.exceptions import EnvironmentConfigError
from demetra.library.models import ChatMessageKind, Context
from demetra.services.chat import record_chat_message, record_chat_status
from demetra.services.linear import (
    post_comment,
    record_linear_comment,
    resolve_state_id,
    update_ticket_status,
)
from demetra.services.runtime.tui import print_message


async def resolve_state(context: Context, state: str) -> str:
    """Resolve the Linear state id a workflow state name refers to.

    The team column named after the state (``awaiting_input`` →
    ``Awaiting Input``) wins over the configured ``LINEAR_STATE_<NAME>_ID``, so a
    stale or mis-pointed id can never park a ticket in a different column. A
    mismatch is reported instead of being applied silently, and the configured
    id is kept whenever the team has no such column.

    Args:
        context: The workflow context.
        state: The Linear state name, e.g. ``"awaiting_input"``.

    Returns:
        str: The resolved Linear state id.

    Raises:
        EnvironmentConfigError: When the state id is not configured at all.
    """
    configured_id = context.environment.linear_state(state)
    try:
        team_id = context.environment.linear_value("team_id")
    except EnvironmentConfigError:
        team_id = None

    resolved_id, warning = await resolve_state_id(name=state, configured_id=configured_id, team_id=team_id)
    if warning:
        print_message(warning, style="warning")
    return resolved_id


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
        await record_chat_status(task_id=context.task.id, state=state)
        return True

    state_id = await resolve_state(context=context, state=state)
    return await update_ticket_status(task_id=context.task.id, state_id=state_id)


async def notify_message(context: Context, body: str, kind: ChatMessageKind = "message") -> bool:
    """Post a message to Linear, or append it to the chat thread.

    Both branches record the message in the local task history, so a task's
    conversation is available locally whichever source it came from.

    A Linear comment that was accepted but could not be mirrored locally is
    not posted again: the local write is best-effort, so the caller still
    records the message as sent, and the mirror restores the missing copy
    from Linear with its comment id on a later run.

    Args:
        context: The workflow context.
        body: The message body.
        kind: The message kind.

    Returns:
        bool: True when the message was stored.
    """
    if context.is_chat:
        return await record_chat_message(task_id=context.task.id, body=body, kind=kind)
    comment_id = await post_comment(task_id=context.task.id, body=body)
    if not comment_id:
        return False
    await record_linear_comment(task_id=context.task.id, body=body, kind=kind, external_id=comment_id)
    return True
