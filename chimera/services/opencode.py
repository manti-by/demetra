from chimera.settings import OPENCODE_PATH
import subprocess

class OpenCodeService:
    def __init__(self):
        self.path = OPENCODE_PATH

    async def plan(self, task: str):
        pass