import subprocess
from pathlib import Path

class GitService:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def get_status(self) -> str:
        result = subprocess.run(["git", "status"], cwd=self.repo_path, capture_output=True)
        return result.stdout.decode()
