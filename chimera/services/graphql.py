import httpx
from typing import Any, Dict

class GraphQLClient:
    def __init__(self, url: str, headers: Dict[str, str] = None):
        self.url = url
        self.headers = headers or {}

    async def execute(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.url, json={"query": query, "variables": variables}, headers=self.headers)
            return resp.json()
