import json

from fastapi import Response

from demetra.library.models import WaitlistedResponse


def waitlisted_response(entry_id: str | None) -> Response:
    """Build the 202 response returned when a user is on the waitlist.

    Args:
        entry_id: The waitlist entry id assigned to the user, if known.

    Returns:
        Response: The 202 JSON response with the waitlisted status.
    """
    waitlisted = WaitlistedResponse(entry_id=entry_id)
    body: dict[str, str | None] = {"status": waitlisted.status, "message": waitlisted.message}
    if waitlisted.entry_id is not None:
        body["entry_id"] = waitlisted.entry_id
    return Response(
        content=json.dumps(body),
        media_type="application/json",
        status_code=202,
    )
