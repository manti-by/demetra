"""
FastAPI app to receive text, process with Groq, and create Linear tickets.
"""

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel

from demetra.services.graphql import graphql_request
from demetra.settings import LINEAR_TEAM_ID


app = FastAPI(
    title="Demetra Ticket Creator",
    description="API to process text with Groq and create Linear tickets",
    version="1.0.0",
)


class TextInput(BaseModel):
    text: str
    project_id: str | None = None
    priority: int = 2  # 0=No priority, 1=Urgent, 2=High, 3=Normal, 4=Low


class TicketResponse(BaseModel):
    success: bool
    ticket_id: str | None = None
    ticket_identifier: str | None = None
    error: str | None = None


async def process_text_with_groq(text: str) -> dict[str, str]:
    """Process raw text with Groq to extract structured ticket information."""

    # Check if Groq API key is set (langchain-groq will read GROQ_API_KEY env var)
    if not os.environ.get("GROQ_API_KEY"):
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    # Initialize Groq LLM
    llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1, max_tokens=2048, max_retries=2)

    # Create prompt template for structuring the ticket
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a technical project manager that converts raw text into structured ticket information.

Given raw text, extract and organize the information into these sections:

1. **Title**: A clear, concise title (max 80 characters)
2. **Description**: A detailed description of the request/issue
3. **Technical Requirements**: Specific technical requirements and constraints
4. **Acceptance Criteria**: Clear, testable criteria for completion

You MUST respond with ONLY valid JSON in this exact format:

{{
  "title": "Clear, actionable title here",
  "description": "Detailed description of the request or issue",
  "technical_requirements": "Specific technical requirements, constraints, and implementation details",
  "acceptance_criteria": "Clear, testable criteria that define when this is complete"
}}

Guidelines:
- Make the title actionable and specific
- Include all relevant details in the description
- Break down technical requirements into clear bullet points using markdown
- Make acceptance criteria testable and specific using bullet points
- If information is missing, make reasonable assumptions based on context
- Focus on what needs to be built/implemented
- Do NOT include any text outside the JSON object
""",
            ),
            ("human", "Raw text: {text}"),
        ]
    )

    try:
        # Process the text
        chain = prompt | llm
        result = await chain.ainvoke({"text": text})

        # Parse the JSON response
        import json

        content = str(result.content)

        # Clean up the response to ensure it's valid JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].strip()

        try:
            parsed = json.loads(content)
            # Ensure all required keys exist
            required_keys = ["title", "description", "technical_requirements", "acceptance_criteria"]
            for key in required_keys:
                if key not in parsed or not parsed[key]:
                    raise ValueError(f"Missing or empty key: {key}")
            return parsed
        except (json.JSONDecodeError, ValueError):
            # Enhanced fallback with better text processing
            lines = text.strip().split("\n")
            text_clean = " ".join(line.strip() for line in lines if line.strip())

            # Try to extract a title from the first meaningful sentence
            title = text_clean.split(".")[0][:80] if text_clean else "Process Request"
            if not title.endswith((".", "?", "!")):
                title = title.strip() + "..."

            return {
                "title": title,
                "description": text_clean[:500] + "..." if len(text_clean) > 500 else text_clean,
                "technical_requirements": "Technical requirements need to be clarified based on the provided description",
                "acceptance_criteria": "Acceptance criteria need to be defined with stakeholders",
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process text with Groq: {e!s}") from e


async def create_linear_ticket(
    title: str,
    description: str,
    technical_requirements: str,
    acceptance_criteria: str,
    project_id: str | None = None,
    priority: int = 2,
) -> dict[str, Any]:
    """Create a Linear ticket with the processed information."""

    # Format the full description
    full_description = f"""## Description

{description}

## Technical Requirements

{technical_requirements}

## Acceptance Criteria

{acceptance_criteria}
"""

    # Create the GraphQL mutation for creating an issue
    create_issue_mutation = """
    mutation CreateIssue($teamId: String!, $title: String!, $description: String!, $priority: Int, $projectId: String) {
        issueCreate(input: {
            teamId: $teamId,
            title: $title,
            description: $description,
            priority: $priority,
            projectId: $projectId
        }) {
            success
            issue {
                id
                identifier
                title
                url
            }
        }
    }
    """

    variables = {"teamId": LINEAR_TEAM_ID, "title": title, "description": full_description, "priority": priority}

    if project_id:
        variables["projectId"] = project_id

    try:
        result = await graphql_request(create_issue_mutation, variables)

        if result.get("data", {}).get("issueCreate", {}).get("success"):
            issue = result["data"]["issueCreate"]["issue"]
            return {
                "success": True,
                "ticket_id": issue["id"],
                "ticket_identifier": issue["identifier"],
                "ticket_url": issue["url"],
            }
        else:
            errors = result.get("errors", [])
            error_msg = "; ".join([error.get("message", "Unknown error") for error in errors])
            return {"success": False, "error": f"Failed to create Linear ticket: {error_msg}"}

    except Exception as e:
        return {"success": False, "error": f"GraphQL request failed: {e!s}"}


@app.post("/create-ticket", response_model=TicketResponse)
async def create_ticket_endpoint(input_data: TextInput) -> TicketResponse:
    """
    Process raw text with Groq and create a structured Linear ticket.

    - **text**: The raw text to process into a ticket
    - **project_id**: Optional Linear project ID to assign the ticket to
    - **priority**: Priority level (0=No priority, 1=Urgent, 2=High, 3=Normal, 4=Low)
    """
    try:
        # Process text with Groq
        processed_data = await process_text_with_groq(input_data.text)

        # Create Linear ticket
        result = await create_linear_ticket(
            title=processed_data["title"],
            description=processed_data["description"],
            technical_requirements=processed_data["technical_requirements"],
            acceptance_criteria=processed_data["acceptance_criteria"],
            project_id=input_data.project_id,
            priority=input_data.priority,
        )

        if result["success"]:
            return TicketResponse(
                success=True, ticket_id=result["ticket_id"], ticket_identifier=result["ticket_identifier"]
            )
        else:
            return TicketResponse(success=False, error=result["error"])

    except Exception as e:
        return TicketResponse(success=False, error=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Demetra Ticket Creator API",
        "version": "1.0.0",
        "endpoints": {
            "/create-ticket": "POST - Create a Linear ticket from raw text",
            "/health": "GET - Health check",
            "/docs": "GET - API documentation",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
