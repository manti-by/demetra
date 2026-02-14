from typing import Any

import aiofiles
import aiohttp

from demetra.settings import BASE_PATH, LINEAR_API_KEY, LINEAR_API_URL


async def get_todo_issues_query() -> str:
    async with aiofiles.open(BASE_PATH / "chimera" / "services" / "queries" / "get_todo_issues.gql") as file:
        content = await file.read()
    return content


async def graphql_request(query: str, variables: dict[str, Any] | None = None) -> dict:
    """Make a GraphQL request to Linear API."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                LINEAR_API_URL,
                json=payload,
                headers={
                    "Authorization": f"{LINEAR_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response.raise_for_status()
                return await response.json()
    except aiohttp.ClientError as e:
        raise Exception(f"Linear API error: {e}") from e
