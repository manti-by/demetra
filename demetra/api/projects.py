import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from demetra.library.models import (
    ENCRYPTED_VALUE_MASK,
    CreateProject,
    Project,
    ProjectEnvironmentEntry,
    ProjectEnvironmentUpsert,
    UpdateProject,
    UserResponse,
    is_sensitive_key,
)
from demetra.services.auth import get_current_user_dep
from demetra.services.persistence.database import (
    create_project,
    delete_project,
    delete_project_environment,
    get_project_by_id,
    get_projects_by_user,
    list_project_environments,
    update_project,
    upsert_project_environment,
)
from demetra.services.runtime.project import cleanup_project_resources, parse_github_url, setup_project


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/projects")

ENV_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")
MAX_ENV_KEY_LENGTH = 128
MAX_ENV_VALUE_LENGTH = 8192


@router.get("", response_model=list[Project])
async def list_projects(user: UserResponse = Depends(get_current_user_dep)):
    """List all projects for the authenticated user.

    Returns a list of projects associated with the user's account,
    including project metadata such as name, state, repository info, and local path.
    """
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


@router.post("", response_model=Project)
async def create_project_endpoint(
    request: CreateProject,
    user: UserResponse = Depends(get_current_user_dep),
):
    """Create a new project with GitHub repository integration.

    Validates the project name and repository URL, then sets up
    the project by cloning the repository and configuring resources.
    Returns the created project with its initial state.
    """
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

    except (SQLAlchemyError, OSError) as e:
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


@router.get("/{project_id}", response_model=Project)
async def get_project_endpoint(
    project_id: str,
    user: UserResponse = Depends(get_current_user_dep),
):
    """Retrieve a specific project by ID.

    Returns the project details including metadata, repository info,
    and current state. Requires authentication and ownership verification.
    """
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


@router.patch("/{project_id}", response_model=Project)
async def update_project_endpoint(
    project_id: str,
    request: UpdateProject,
    user: UserResponse = Depends(get_current_user_dep),
):
    """Update an existing project's properties.

    Allows updating the project name, repository URL, and Linear project ID.
    Validates ownership before applying changes.
    """
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


@router.delete("/{project_id}")
async def delete_project_endpoint(
    project_id: str,
    user: UserResponse = Depends(get_current_user_dep),
):
    """Delete a project and its associated resources.

    Removes the project from the database and cleans up any
    associated local resources. Requires authentication and ownership.
    """
    if not await delete_project(project_id=project_id, user_id=user.id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted successfully"}


@router.get("/{project_id}/environment", response_model=list[ProjectEnvironmentEntry])
async def list_project_environment_endpoint(
    project_id: str,
    user: UserResponse = Depends(get_current_user_dep),
):
    """List environment variables for a specific project.

    Returns a list of key-value entries configured for the project.
    Requires authentication and ownership verification.
    """
    try:
        entries = await list_project_environments(project_id=project_id, user_id=user.id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail="Project not found") from e

    return [
        ProjectEnvironmentEntry(
            id=entry["id"],
            project_id=entry["project_id"],
            key=entry["key"],
            value=ENCRYPTED_VALUE_MASK if is_sensitive_key(entry["key"]) else entry["value"],
            type=entry["type"],
        )
        for entry in entries
    ]


@router.put("/{project_id}/environment/{key}", response_model=ProjectEnvironmentEntry)
async def upsert_project_environment_endpoint(
    project_id: str,
    key: str,
    request: ProjectEnvironmentUpsert,
    user: UserResponse = Depends(get_current_user_dep),
):
    """Create or update a single environment variable for a project.

    Saves the provided key-value pair and returns the resulting entry.
    Encrypted values are stored encrypted and returned masked.
    Requires authentication and ownership verification.
    """
    validated_key = key.strip()
    if not validated_key:
        raise HTTPException(status_code=400, detail="Environment key cannot be empty")
    if len(validated_key) > MAX_ENV_KEY_LENGTH:
        raise HTTPException(status_code=400, detail="Environment key must be at most 128 characters")
    if not ENV_KEY_RE.fullmatch(validated_key):
        raise HTTPException(status_code=400, detail="Environment key must match [A-Za-z_][A-Za-z0-9_.-]*")

    if request.type not in ("text", "encrypted"):
        raise HTTPException(status_code=400, detail="Environment type must be 'text' or 'encrypted'")

    if len(request.value) > MAX_ENV_VALUE_LENGTH:
        raise HTTPException(status_code=400, detail="Environment value must be at most 8192 characters")

    if request.type == "text" and "\x00" in request.value:
        raise HTTPException(status_code=400, detail="Environment value cannot contain NUL bytes")

    try:
        entry = await upsert_project_environment(
            project_id=project_id,
            user_id=user.id,
            key=validated_key,
            value=request.value,
            env_type=request.type,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail="Project not found") from e

    return ProjectEnvironmentEntry(
        id=entry["id"],
        project_id=entry["project_id"],
        key=entry["key"],
        value=ENCRYPTED_VALUE_MASK if is_sensitive_key(entry["key"]) else entry["value"],
        type=entry["type"],
    )


@router.delete("/{project_id}/environment/{key}")
async def delete_project_environment_endpoint(
    project_id: str,
    key: str,
    user: UserResponse = Depends(get_current_user_dep),
):
    """Delete a single environment variable from a project.

    Requires authentication and ownership verification.
    """
    validated_key = key.strip()
    if not validated_key:
        raise HTTPException(status_code=400, detail="Environment key cannot be empty")

    try:
        await delete_project_environment(
            project_id=project_id,
            user_id=user.id,
            key=validated_key,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail="Project not found") from e

    return {"message": "Environment variable deleted successfully"}
