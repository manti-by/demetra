import subprocess
from pathlib import Path
from typing import Optional, List

class OpenCodeService:
    def __init__(self, path: str = "/usr/local/bin/opencode"):
        self.path = path

    async def plan(self, task: str) -> Optional[str]:
        result = subprocess.run([self.path, "plan", task], capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else None

    async def build(self, plan_file: str) -> bool:
        result = subprocess.run([self.path, "build", "-f", plan_file], capture_output=True)
        return result.returncode == 0
