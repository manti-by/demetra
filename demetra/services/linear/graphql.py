from typing import Any

import aiofiles
import aiohttp

from demetra.library.exceptions import LinearError
from demetra.services.linear.oauth import get_valid_token
from demetra.settings import BASE_PATH, LINEAR


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


async def graphql_request(query: str, variables: dict[str, Any] | None = None) -> dict:
    """Send a GraphQL request to the Linear API and return its raw payload.

    Resolves a valid OAuth token automatically.

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

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                LINEAR["api_url"],
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response.raise_for_status()
                data = await response.json()
    except aiohttp.ClientError as e:
        raise LinearError(f"Linear API error: {e}") from e

    if not isinstance(data, dict):
        raise LinearError(f"Linear API returned an unexpected payload: {data!r}")

    return data
