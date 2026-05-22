from fastapi import APIRouter, Cookie, HTTPException

from demetra.library.models import CreateTicket, Ticket
from demetra.services.auth import get_current_user
from demetra.services.groq import process_text_with_groq
from demetra.services.linear import create_linear_ticket
from demetra.services.utils import get_project_id_by_name
from demetra.settings import LINEAR


router = APIRouter(prefix="/api/v1/tickets")


@router.post("", response_model=Ticket)
async def create_ticket(request: CreateTicket, auth_token: str | None = Cookie(default=None)):
    """Create a new ticket in Linear using AI-processed text.

    Accepts raw text input, processes it through Groq AI to extract
    structured ticket details (title, description, requirements, criteria),
    and creates the ticket in the specified Linear project.
    """
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not await get_current_user(token=auth_token):
        raise HTTPException(status_code=401, detail="Invalid token")

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        processed = await process_text_with_groq(request.text)

        if "tech_requirements" in processed:
            processed["technical_requirements"] = processed.pop("tech_requirements")
        if "acceptance" in processed and "acceptance_criteria" not in processed:
            processed["acceptance_criteria"] = processed.pop("acceptance")

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
