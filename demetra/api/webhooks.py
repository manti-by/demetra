import logging

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from demetra.services.github import verify_signature, webhook_rebase_handler
from demetra.services.queue import queue


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks")


@router.post("/github")
async def github_webhook(request: Request, x_hub_signature_256: str | None = Header(default=None)):
    """Handle incoming GitHub webhook events.

    Verifies the request signature, and for ``issue_comment`` events enqueues
    the rebase handler for async processing.

    Args:
        request: The incoming webhook request.
        x_hub_signature_256: The GitHub signature header used for verification.

    Returns:
        JSONResponse: 401 when the signature is invalid, otherwise a status
            JSON object describing whether the event was accepted or ignored.
    """
    payload_body = await request.body()
    if not verify_signature(payload_body=payload_body, signature_header=x_hub_signature_256):
        return JSONResponse(status_code=401, content={"error": "Invalid signature"})

    payload = await request.json()
    event = request.headers.get("X-GitHub-Event", "")

    logger.info("Received GitHub webhook event: %s", event)

    if event != "issue_comment":
        return {"status": "ignored", "reason": f"unhandled event: {event}"}

    queue.enqueue(webhook_rebase_handler, payload=payload)

    return {"status": "accepted"}
