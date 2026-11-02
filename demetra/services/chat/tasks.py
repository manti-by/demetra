from demetra.library.models import Chat, ChatMessage, LinearTask
from demetra.services.linear import get_linear_task_by_id
from demetra.services.persistence.database import (
    get_chat_by_task_id,
    get_project_by_id_system,
    list_chat_messages,
)


TASK_CONTEXT_MESSAGE_KINDS = ("message", "question")


def build_chat_task(*, chat: Chat, project_name: str | None, messages: list[ChatMessage]) -> LinearTask:
    """Build a ``LinearTask``-shaped record from a chat-mode task.

    The pipeline is written against :class:`LinearTask`, so chat mode adapts its
    stored data instead of branching every workflow. Only user messages and
    plan questions feed the agent context; workflow output (plans, failures,
    research reports) stays in the thread but is not replayed as task comments.

    Args:
        chat: The chat record backing the session.
        project_name: The project name the chat runs against.
        messages: The chat thread in recording order.

    Returns:
        LinearTask: The chat task adapted for the workflow.
    """
    comments = [message.body for message in messages if message.kind in TASK_CONTEXT_MESSAGE_KINDS]
    return LinearTask(
        id=chat.session_task_id,
        identifier=chat.session_task_id,
        title=chat.title,
        description=chat.description,
        priority=0,
        created_at=chat.created_at,
        project_name=project_name,
        project_id=chat.project_id,
        user_id=chat.user_id,
        comments=comments,
        labels=list(chat.tags),
        url=None,
    )


async def get_chat_task(task_id: str) -> tuple[LinearTask, Chat] | None:
    """Resolve a chat-mode task and its record from a task id.

    Args:
        task_id: The ``CH-<id>`` task id.

    Returns:
        tuple[LinearTask, Chat] | None: The adapted task and its chat record, or
            None when the task is not chat-mode.
    """
    chat = await get_chat_by_task_id(task_id=task_id)
    if chat is None:
        return None

    project = await get_project_by_id_system(project_id=chat.project_id)
    messages = await list_chat_messages(task_id=task_id)
    task = build_chat_task(chat=chat, project_name=project["name"] if project else None, messages=messages)
    return task, chat


async def resolve_task_by_id(task_id: str) -> LinearTask | None:
    """Resolve a task id from either task source.

    Args:
        task_id: A chat ``CH-<id>`` task id or a Linear issue id.

    Returns:
        LinearTask | None: The chat task when one exists, otherwise the Linear
            task, or None when neither resolves.
    """
    chat_task = await get_chat_task(task_id=task_id)
    if chat_task is not None:
        return chat_task[0]
    return await get_linear_task_by_id(task_id=task_id)
