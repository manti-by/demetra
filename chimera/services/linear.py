import httpx
from chimera.settings import LINEAR_API_KEY

class LinearClient:
    def __init__(self):
        self.api_key = LINEAR_API_KEY
