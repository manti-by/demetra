from fastapi import APIRouter

from demetra.library.models import ChatTemplate
from demetra.services.runtime.template import list_chat_templates


router = APIRouter(prefix="/api/v1/chat-templates")


@router.get("", response_model=list[ChatTemplate])
async def list_chat_templates_endpoint() -> list[ChatTemplate]:
    """Return the chat templates available in the new-chat form.

    The templates are static repository content with no user data, so the
    endpoint is public.

    Returns:
        list[ChatTemplate]: The available chat templates with their full
            content.
    """
    return await list_chat_templates()
