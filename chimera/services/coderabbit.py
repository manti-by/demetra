import subprocess
from pathlib import Path

class CodeRabbitService:
    def __init__(self, path: str = "/usr/local/bin/coderabbit"):
        self.path = path

    async def review(self, repo_path: Path) -> dict:
        result = subprocess.run([self.path, "review", str(repo_path)], capture_output=True, text=True)
        return {"output": result.stdout, "returncode": result.returncode}
