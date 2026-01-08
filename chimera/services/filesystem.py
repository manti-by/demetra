from pathlib import Path
from typing import List

class FilesystemService:
    def __init__(self, base_path: Path):
        self.base_path = base_path

    def list_projects(self) -> List[str]:
        return [p.name for p in self.base_path.iterdir() if p.is_dir()]

    def validate_project(self, name: str) -> bool:
        return (self.base_path / name).exists()
