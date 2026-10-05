from typing import Any

import aiohttp

from demetra.library.exceptions import ClickUpConfigError, ClickUpError
from demetra.settings import CLICKUP


REQUEST_TIMEOUT_SECONDS = 10


def get_api_token() -> str:
    """Return the configured ClickUp API token.

    Personal tokens (``pk_...``) are sent verbatim in the ``Authorization``
    header; ClickUp does not use a ``Bearer`` prefix for them.

    Returns:
        str: The API token.

    Raises:
        ClickUpConfigError: When ``CLICKUP_API_TOKEN`` is not set.
    """
    token = CLICKUP["api_token"]
    if not token:
        raise ClickUpConfigError("CLICKUP_API_TOKEN must be set")
    return token


async def clickup_request(
    method: str,
    path: str,
    params: dict[str, Any] | list[tuple[str, Any]] | None = None,
    json: dict[str, Any] | None = None,
) -> dict:
    """Send a request to the ClickUp REST API and return its JSON payload.

    Args:
        method: The HTTP method, e.g. ``"GET"`` or ``"PUT"``.
        path: The API path relative to the v2 base URL, e.g. ``"/task/abc"``.
        params: Optional query parameters. A list of tuples allows repeated
            keys such as ``statuses[]``.
        json: Optional JSON request body.

    Returns:
        dict: The decoded JSON response payload.

    Raises:
        ClickUpConfigError: When the API token is not configured.
        ClickUpError: When the request fails or the payload is unexpected.
    """
    token = get_api_token()
    url = f"{CLICKUP['api_url']}{path}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                params=params,
                json=json,
                headers={"Authorization": token, "Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
            ) as response:
                if response.status >= 400:
                    detail = await response.text()
                    raise ClickUpError(f"ClickUp API error {response.status} for {method} {path}: {detail[:500]}")
                data = await response.json()
    except aiohttp.ClientError as e:
        raise ClickUpError(f"ClickUp API error: {e}") from e

    if not isinstance(data, dict):
        raise ClickUpError(f"ClickUp API returned an unexpected payload: {data!r}")

    return data
