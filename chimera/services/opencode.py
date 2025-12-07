from typing import Optional
import subprocess

class OpenCodeService:
    def __init__(self, path: str = "/usr/local/bin/opencode"):
        self.path = path

    async def plan(self, task: str) -> Optional[str]:
        pass
