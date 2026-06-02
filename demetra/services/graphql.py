from typing import Any

import aiofiles
import aiohttp

from demetra.library.exceptions import LinearError
from demetra.services.oauth import get_valid_token
from demetra.settings import BASE_PATH, LINEAR


async def get_query(name: str) -> str:
    async with aiofiles.open(BASE_PATH / f"demetra/queries/{name}.gql") as file:
        content = await file.read()
    return content


async def graphql_request(query: str, variables: dict[str, Any] | None = None) -> dict:
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
                return await response.json()
    except aiohttp.ClientError as e:
        raise LinearError(f"Linear API error: {e}") from e
