import os
from pathlib import Path

from chimera.settings import PROJECTS_PATH


async def get_project_root(project_name: str) -> Path:
    projects = {path: Path(PROJECTS_PATH) / path for path in os.listdir(path=PROJECTS_PATH)}
    if project_name not in projects:
        raise ValueError(f"Project '{project_name}' not found")
    return projects[project_name]
