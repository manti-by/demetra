from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from demetra.services.groq import process_text_with_groq
from demetra.services.linear import create_linear_ticket


app = FastAPI(title="Demetra Ticket API")


class TicketRequest(BaseModel):
    text: str
    title: str | None = None


class TicketResponse(BaseModel):
    ticket_id: str
    identifier: str
    title: str


@app.post("/ticket", response_model=TicketResponse)
async def create_ticket(request: TicketRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        processed = await process_text_with_groq(request.text)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    title = request.title if request.title else processed["title"]
    if not title:
        title = request.text[:100]

    try:
        ticket = await create_linear_ticket(
            title=title,
            description=processed["description"],
            tech_requirements=processed["tech_requirements"],
            acceptance_criteria=processed["acceptance_criteria"],
        )
    except TypeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except KeyError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return TicketResponse(**ticket)
