from typing import Any

import aiofiles
import aiohttp

from demetra.exceptions import LinearError
from demetra.services.oauth import get_valid_token
from demetra.settings import BASE_PATH, LINEAR_API_KEY, LINEAR_API_URL


async def get_query(name: str) -> str:
    async with aiofiles.open(BASE_PATH / f"demetra/queries/{name}.gql") as file:
        content = await file.read()
    return content


async def graphql_request(query: str, variables: dict[str, Any] | None = None) -> dict:
    token = await get_valid_token()

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                LINEAR_API_URL,
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


async def graphql_request_with_api_key(query: str, variables: dict[str, Any] | None = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                LINEAR_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {LINEAR_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                response.raise_for_status()
                return await response.json()
    except aiohttp.ClientError as e:
        raise LinearError(f"Linear API error: {e}") from e
