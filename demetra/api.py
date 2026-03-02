from fastapi import FastAPI, HTTPException

from demetra.models import TicketRequest, TicketResponse
from demetra.services.groq import process_text_with_groq
from demetra.services.linear import create_linear_ticket
from demetra.services.utils import get_project_id_by_name
from demetra.settings import LINEAR_DEFAULT_PROJECT_ID


app = FastAPI(title="Demetra Ticket API")


@app.post("/api/v1/tickets/", response_model=TicketResponse)
async def create_ticket(request: TicketRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        processed = await process_text_with_groq(request.text)

        project_name = processed["project_name"]
        project_id = await get_project_id_by_name(project_name) or LINEAR_DEFAULT_PROJECT_ID

        ticket = await create_linear_ticket(
            title=processed["title"],
            description=processed["description"],
            tech_requirements=processed["tech_requirements"],
            acceptance_criteria=processed["acceptance_criteria"],
            project_id=project_id,
        )
    except (TypeError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return TicketResponse(**ticket)
