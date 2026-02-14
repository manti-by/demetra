import os
from pathlib import Path

from demetra.settings import PROJECTS_PATH


def get_project_root(project_name: str) -> Path:
    projects = {path: Path(PROJECTS_PATH) / path for path in os.listdir(path=PROJECTS_PATH)}
    if project_name not in projects:
        raise ValueError(f"Project '{project_name}' not found")
    return projects[project_name]
