"""Project management endpoints."""

import logging

from fastapi import APIRouter, Cookie, HTTPException

from demetra.library.models import CreateProject, Project, UpdateProject
from demetra.services.auth import get_current_user
from demetra.services.database import (
    create_project,
    delete_project,
    get_project_by_id,
    get_projects_by_user,
    update_project,
)
from demetra.services.project import cleanup_project_resources, parse_github_url, setup_project


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/v1/projects", response_model=list[Project])
async def list_projects(auth_token: str | None = Cookie(default=None)):
    """List all projects for the authenticated user.

    Returns a list of projects associated with the user's account,
    including project metadata such as name, state, repository info, and local path.
    """
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    projects = await get_projects_by_user(user_id=user.id)
    return [
        Project(
            id=p["id"],
            user_id=p.get("user_id"),
            linear_project_id=p.get("linear_project_id"),
            name=p["name"],
            state=p["state"],
            repository_url=p["repository_url"],
            repository_name=p["repository_name"],
            repository_owner=p["repository_owner"],
            local_path=p["local_path"],
            created_at=p["created_at"].isoformat() if p.get("created_at") else "",
            updated_at=p["updated_at"].isoformat() if p.get("updated_at") else "",
        )
        for p in projects
    ]


@router.post("/api/v1/projects", response_model=Project)
async def create_project_endpoint(
    request: CreateProject,
    auth_token: str | None = Cookie(default=None),
):
    """Create a new project with GitHub repository integration.

    Validates the project name and repository URL, then sets up
    the project by cloning the repository and configuring resources.
    Returns the created project with its initial state.
    """
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    if not (project_name := request.name.strip()):
        raise HTTPException(status_code=400, detail="Project name cannot be empty")

    if not (repository_url := request.repository_url.strip()):
        raise HTTPException(status_code=400, detail="Repository URL cannot be empty")

    if not (parsed_repository_url := parse_github_url(repository_url)):
        raise HTTPException(status_code=400, detail=f"Invalid GitHub repository URL: {repository_url}")

    repository_owner, repository_name = parsed_repository_url
    project = await create_project(
        user_id=user.id,
        name=project_name,
        repository_url=repository_url,
        repository_name=repository_name,
        repository_owner=repository_owner,
        linear_project_id=request.linear_project_id,
        state="provisioning",
    )

    project_id, linear_project_id = project["id"], request.linear_project_id
    try:
        setup_info = await setup_project(project=project)
        local_path = setup_info["local_path"]

    except ValueError as e:
        logging.error(f"Failed to setup project: {e}")
        await cleanup_project_resources(project=project)
        await update_project(project_id=project_id, user_id=user.id, state="failed")
        raise HTTPException(status_code=400, detail="Invalid project name or repository URL") from e

    except Exception as e:
        logging.exception(f"Failed to setup project: {e}")
        await cleanup_project_resources(project=project)
        await update_project(project_id=project_id, user_id=user.id, state="failed")
        raise HTTPException(status_code=500, detail="Internal server error") from e

    if not (
        updated_project := await update_project(
            project_id=project_id, user_id=user.id, local_path=local_path, state="active"
        )
    ):
        raise HTTPException(status_code=500, detail="Failed to update project state")

    return Project(
        id=project_id,
        user_id=user.id,
        name=project_name,
        state=updated_project["state"],
        repository_url=repository_url,
        repository_name=repository_name,
        repository_owner=repository_owner,
        linear_project_id=linear_project_id,
        local_path=local_path,
        created_at=updated_project["created_at"],
        updated_at=updated_project["updated_at"],
    )


@router.get("/api/v1/projects/{project_id}", response_model=Project)
async def get_project_endpoint(
    project_id: str,
    auth_token: str | None = Cookie(default=None),
):
    """Retrieve a specific project by ID.

    Returns the project details including metadata, repository info,
    and current state. Requires authentication and ownership verification.
    """
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not (project := await get_project_by_id(project_id=project_id, user_id=user.id)):
        raise HTTPException(status_code=404, detail="Project not found")

    return Project(
        id=project["id"],
        user_id=project.get("user_id"),
        linear_project_id=project.get("linear_project_id"),
        name=project["name"],
        state=project["state"],
        repository_url=project["repository_url"],
        repository_name=project["repository_name"],
        repository_owner=project["repository_owner"],
        local_path=project["local_path"],
        created_at=project["created_at"].isoformat() if project.get("created_at") else "",
        updated_at=project["updated_at"].isoformat() if project.get("updated_at") else "",
    )


@router.patch("/api/v1/projects/{project_id}", response_model=Project)
async def update_project_endpoint(
    project_id: str,
    request: UpdateProject,
    auth_token: str | None = Cookie(default=None),
):
    """Update an existing project's properties.

    Allows updating the project name, repository URL, and Linear project ID.
    Validates ownership before applying changes.
    """
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    validated_name = request.name.strip() if request.name else None
    if validated_name == "":
        raise HTTPException(status_code=400, detail="Project name cannot be empty")

    validated_repository_url = request.repository_url.strip() if request.repository_url else None
    if validated_repository_url and not parse_github_url(validated_repository_url):
        raise HTTPException(status_code=400, detail=f"Invalid GitHub repository URL: {validated_repository_url}")

    project = await update_project(
        project_id=project_id,
        user_id=user.id,
        name=validated_name,
        repository_url=validated_repository_url,
        linear_project_id=request.linear_project_id,
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return Project(
        id=project["id"],
        user_id=project["user_id"],
        linear_project_id=project.get("linear_project_id"),
        name=project["name"],
        state=project["state"],
        repository_url=project["repository_url"],
        repository_name=project["repository_name"],
        repository_owner=project["repository_owner"],
        local_path=project["local_path"],
        created_at=project["created_at"].isoformat() if project.get("created_at") else "",
        updated_at=project["updated_at"].isoformat() if project.get("updated_at") else "",
    )


@router.delete("/api/v1/projects/{project_id}")
async def delete_project_endpoint(
    project_id: str,
    auth_token: str | None = Cookie(default=None),
):
    """Delete a project and its associated resources.

    Removes the project from the database and cleans up any
    associated local resources. Requires authentication and ownership.
    """
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    await delete_project(project_id=project_id, user_id=user.id)
    return {"message": "Project deleted successfully"}
