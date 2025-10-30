from chimera.settings import LINEAR_API_KEY, LINEAR_API_URL
import httpx

class LinearClient:
    def __init__(self):
        self.api_key = LINEAR_API_KEY
        self.url = LINEAR_API_URL

    async def get_issues(self, team_id: str):
        pass