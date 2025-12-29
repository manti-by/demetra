import httpx
from chimera.settings import LINEAR_API_KEY, LINEAR_API_URL

class LinearClient:
    def __init__(self):
        self.api_key = LINEAR_API_KEY
        self.url = LINEAR_API_URL

    async def request(self, query: str, variables: dict = None):
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.url, json={"query": query, "variables": variables}, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Linear API error: {e}")
