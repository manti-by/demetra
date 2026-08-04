import os
from pathlib import Path

from demetra.library.exceptions import ProjectDoesNotExistsError, SettingsError
from demetra.settings import PROJECTS_PATH


def get_project_root(project_name: str) -> Path:
    """Return the filesystem root of a project directory.

    Deprecated; kept for backward compatibility.

    Args:
        project_name: The name of the project directory.

    Returns:
        Path: The project directory path.

    Raises:
        SettingsError: When the projects directory is missing or not a
            directory.
        ProjectDoesNotExistsError: When the named project does not exist.
    """
    # TODO: Deprecated since 28-04-2026, remove after 28-07-2026
    if not PROJECTS_PATH.exists():
        raise SettingsError(f"Projects directory '{PROJECTS_PATH}' does not exist")
    if not PROJECTS_PATH.is_dir():
        raise SettingsError(f"Projects path '{PROJECTS_PATH}' is not a directory")

    projects = {path: Path(PROJECTS_PATH) / path for path in os.listdir(path=PROJECTS_PATH)}
    if project_name not in projects:
        raise ProjectDoesNotExistsError(f"Project '{project_name}' not found")
    return projects[project_name]
