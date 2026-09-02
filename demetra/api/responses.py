import json

from fastapi import Request, Response

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


def delete_cookie_header(name: str) -> dict[str, str]:
    """Build a Set-Cookie header that expires the named cookie.

    Raised HTTPException responses bypass the endpoint's response object, so
    a cookie deletion must travel as a header on the error itself.

    Args:
        name: The cookie to expire.

    Returns:
        dict[str, str]: Headers dict carrying the Set-Cookie header.
    """
    probe = Response()
    probe.delete_cookie(key=name)
    return {"Set-Cookie": probe.headers["set-cookie"]}


def client_host(request: Request) -> str:
    """Return the client IP of the request.

    Args:
        request: The incoming request.

    Returns:
        str: The client IP, or a shared placeholder when unknown.
    """
    return request.client.host if request.client else "unknown"
