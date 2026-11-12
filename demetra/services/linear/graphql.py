import asyncio
from typing import Any

import aiofiles
import aiohttp

from demetra.library.exceptions import LinearError
from demetra.services.linear.oauth import get_valid_token
from demetra.settings import BASE_PATH, LINEAR


RATE_LIMIT_RETRIES = 3
RATE_LIMIT_BACKOFF_SECONDS = 1.0


async def get_query(name: str) -> str:
    """Load a GraphQL query document from the queries directory.

    Args:
        name: The query file name without extension.

    Returns:
        str: The GraphQL query string.
    """
    async with aiofiles.open(BASE_PATH / f"demetra/queries/{name}.gql") as file:
        content = await file.read()
    return content


def _retry_after_seconds(response: aiohttp.ClientResponse, attempt: int) -> float:
    """Return the delay before the next attempt of a rate-limited request.

    Linear answers a throttled request with a ``Retry-After`` header. The
    header is honoured when it holds a number of seconds, otherwise the delay
    grows exponentially.

    Args:
        response: The rate-limited response.
        attempt: The zero-based number of the attempt that was throttled.

    Returns:
        float: The delay in seconds.
    """
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return RATE_LIMIT_BACKOFF_SECONDS * (2**attempt)


async def _post_graphql(url: str, payload: dict, headers: dict) -> Any:
    """Send a GraphQL request, retrying a rate-limited response.

    Args:
        url: The GraphQL endpoint.
        payload: The request payload.
        headers: The request headers.

    Returns:
        Any: The decoded response body.

    Raises:
        LinearError: When every attempt was rate limited.
    """
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 429 and attempt < RATE_LIMIT_RETRIES:
                    await asyncio.sleep(_retry_after_seconds(response=response, attempt=attempt))
                    continue
                response.raise_for_status()
                return await response.json()
    raise LinearError("Linear API kept rate limiting the request")


async def graphql_request(query: str, variables: dict[str, Any] | None = None) -> dict:
    """Send a GraphQL request to the Linear API and return its raw payload.

    Resolves a valid OAuth token automatically. A rate-limited request is
    repeated after the delay Linear asks for, so a throttled call does not
    fail the caller.

    Args:
        query: The GraphQL query string.
        variables: Optional query variables.

    Returns:
        dict: The raw JSON response payload.

    Raises:
        LinearError: When the request fails or the payload is unexpected.
    """
    token = await get_valid_token()

    payload = {"query": query}
    if variables is not None:
        payload["variables"]: dict[str, Any] = variables  # ty: ignore

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        data = await _post_graphql(url=LINEAR["api_url"], payload=payload, headers=headers)
    except aiohttp.ClientError as e:
        raise LinearError(f"Linear API error: {e}") from e

    if not isinstance(data, dict):
        raise LinearError(f"Linear API returned an unexpected payload: {data!r}")

    return data
