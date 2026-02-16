import os
from pathlib import Path

from demetra.exceptions import ProjectDoesNotExistsError, SettingsError
from demetra.settings import PROJECTS_PATH


def get_project_root(project_name: str) -> Path:
    if not PROJECTS_PATH.exists():
        raise SettingsError(f"Projects directory '{PROJECTS_PATH}' does not exist")
    if not PROJECTS_PATH.is_dir():
        raise SettingsError(f"Projects path '{PROJECTS_PATH}' is not a directory")

    projects = {path: Path(PROJECTS_PATH) / path for path in os.listdir(path=PROJECTS_PATH)}
    if project_name not in projects:
        raise ProjectDoesNotExistsError(f"Project '{project_name}' not found")
    return projects[project_name]
