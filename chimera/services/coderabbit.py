from chimera.settings import CODERABBIT_PATH
import subprocess

class CodeRabbitService:
    def __init__(self):
        self.path = CODERABBIT_PATH

    async def review(self, repo_path: str):
        pass