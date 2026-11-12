from demetra.library.models import Chat, ChatMessage, Message, Task
from demetra.services.linear import get_linear_task_by_id
from demetra.services.persistence.database import (
    get_chat_by_task_id,
    get_project_by_id_system,
    list_chat_messages,
)


TASK_CONTEXT_MESSAGE_KINDS = ("message", "question")


def build_chat_task(*, chat: Chat, project_name: str | None, messages: list[ChatMessage]) -> Chat:
    """Build the task context of a chat-mode session.

    Only user messages and plan questions feed the agent context; workflow
    output (plans, failures, research reports) stays in the thread but is not
    replayed as task messages.

    Args:
        chat: The chat record backing the session.
        project_name: The project name the chat runs against.
        messages: The chat thread in recording order.

    Returns:
        Chat: The chat task carrying its context messages.
    """
    context_messages = [
        Message(
            id=message.id,
            task_id=message.task_id,
            body=message.body,
            created_at=message.created_at,
            parent_id=message.parent_id,
            source=message.source,
            external_id=message.external_id,
            author_id=message.author_id,
            author_name=message.author_name,
            is_system=message.is_system,
            kind=message.kind,
        )
        for message in messages
        if message.kind in TASK_CONTEXT_MESSAGE_KINDS
    ]
    return Chat(
        id=chat.id,
        chat_id=chat.chat_id,
        identifier=chat.identifier,
        title=chat.title,
        description=chat.description,
        priority=chat.priority,
        state=chat.state,
        url=chat.url,
        tags=list(chat.tags),
        project_id=chat.project_id,
        project_name=project_name,
        user_id=chat.user_id,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        messages=context_messages,
    )


async def get_chat_task(task_id: str) -> tuple[Chat, Chat] | None:
    """Resolve a chat-mode task and its record from a task id.

    Args:
        task_id: The ``CH-<id>`` task id.

    Returns:
        tuple[Chat, Chat] | None: The task and its chat record, or None when
            the task is not chat-mode.
    """
    chat = await get_chat_by_task_id(task_id=task_id)
    if chat is None:
        return None

    project = await get_project_by_id_system(project_id=chat.project_id) if chat.project_id else None
    messages = await list_chat_messages(task_id=task_id)
    task = build_chat_task(chat=chat, project_name=project["name"] if project else None, messages=messages)
    return task, chat


async def resolve_task_by_id(task_id: str) -> Task | None:
    """Resolve a task id from either task source.

    Args:
        task_id: A chat ``CH-<id>`` task id or a Linear issue id.

    Returns:
        Task | None: The chat task when one exists, otherwise the Linear
            task, or None when neither resolves.
    """
    chat_task = await get_chat_task(task_id=task_id)
    if chat_task is not None:
        return chat_task[0]
    return await get_linear_task_by_id(task_id=task_id)
