from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Query

from demetra.library.models import CreateTicket, Ticket
from demetra.services.auth import get_current_user
from demetra.services.database import get_sessions
from demetra.services.groq import process_text_with_groq
from demetra.services.linear import create_linear_ticket
from demetra.services.utils import get_project_id_by_name
from demetra.settings import LINEAR


router = APIRouter()


@router.post("/api/v1/tickets", response_model=Ticket)
async def create_ticket(request: CreateTicket, auth_token: str | None = Cookie(default=None)):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not await get_current_user(token=auth_token):
        raise HTTPException(status_code=401, detail="Invalid token")

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        processed = await process_text_with_groq(request.text)

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


@router.get("/api/v1/sessions")
async def list_sessions(
    auth_token: str | None = Cookie(default=None),
    status: Annotated[str | None, Query()] = None,
) -> list[dict]:
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    if status and status not in ("pending", "processed", "failed"):
        raise HTTPException(status_code=400, detail="Invalid status. Must be one of: pending, processed, failed")

    sessions = await get_sessions(user_id=user.id, status=status)
    return sessions
