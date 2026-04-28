from fastapi import Cookie, HTTPException

from demetra.api import app
from demetra.library.models import ProjectRequest, ProjectResponse, ProjectUpdateRequest
from demetra.services.auth import get_current_user
from demetra.services.database import (
    create_project,
    delete_project,
    get_project_by_id,
    get_projects_by_user,
    update_project,
)
from demetra.services.project import cleanup_project_resources, setup_project


@app.get("/api/v1/projects", response_model=list[ProjectResponse])
async def list_projects(auth_token: str | None = Cookie(default=None)):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    projects = await get_projects_by_user(user_id=user.id)
    return [
        ProjectResponse(
            id=p["id"],
            user_id=p.get("user_id"),
            linear_project_id=p.get("linear_project_id"),
            name=p["name"],
            repository_url=p["repository_url"],
            local_path=p.get("local_path"),
            created_at=p["created_at"].isoformat() if p.get("created_at") else "",
            updated_at=p["updated_at"].isoformat() if p.get("updated_at") else "",
        )
        for p in projects
    ]


@app.post("/api/v1/projects", response_model=ProjectResponse)
async def create_project_endpoint(
    request: ProjectRequest,
    auth_token: str | None = Cookie(default=None),
):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid token")

    if not (project_name := request.name.strip()):
        raise HTTPException(status_code=400, detail="Project name cannot be empty")

    if not (repository_url := request.repository_url.strip()):
        raise HTTPException(status_code=400, detail="Repository URL cannot be empty")

    project = await create_project(
        user_id=user.id,
        name=project_name,
        repository_url=repository_url,
        linear_project_id=request.linear_project_id,
        state="provisioning",
    )

    project_id, linear_project_id = project["id"], request.linear_project_id
    try:
        setup_info = await setup_project(
            project_id=project_id, project_name=project_name, repository_url=repository_url
        )
        local_path = setup_info["local_path"]

    except ValueError:
        await cleanup_project_resources(project_id=project_id, project_name=project_name, repository_url=repository_url)
        raise HTTPException(status_code=400, detail="Invalid project name or repository URL") from None

    except Exception as e:
        import logging

        logging.exception(f"Failed to setup project: {e}")
        await cleanup_project_resources(project_id=project_id, project_name=project_name, repository_url=repository_url)
        await update_project(project_id=project_id, user_id=user.id, state="failed")
        raise HTTPException(status_code=500, detail="Internal server error") from None

    if not (
        updated_project := await update_project(
            project_id=project_id, user_id=user.id, local_path=local_path, state="active"
        )
    ):
        raise HTTPException(status_code=500, detail="Failed to update project state")

    return ProjectResponse(
        id=project_id,
        user_id=user.id,
        name=project_name,
        repository_url=repository_url,
        linear_project_id=linear_project_id,
        local_path=local_path,
        created_at=updated_project["created_at"],
        updated_at=updated_project["updated_at"],
    )


@app.get("/api/v1/projects/{project_id}", response_model=ProjectResponse)
async def get_project_endpoint(
    project_id: str,
    auth_token: str | None = Cookie(default=None),
):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not (project := await get_project_by_id(project_id=project_id, user_id=user.id)):
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectResponse(
        id=project["id"],
        user_id=project.get("user_id"),
        linear_project_id=project.get("linear_project_id"),
        name=project["name"],
        repository_url=project["repository_url"],
        local_path=project.get("local_path"),
        created_at=project["created_at"].isoformat() if project.get("created_at") else "",
        updated_at=project["updated_at"].isoformat() if project.get("updated_at") else "",
    )


@app.patch("/api/v1/projects/{project_id}", response_model=ProjectResponse)
async def update_project_endpoint(
    project_id: str,
    request: ProjectUpdateRequest,
    auth_token: str | None = Cookie(default=None),
):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    project = await update_project(
        project_id=project_id,
        user_id=user.id,
        name=request.name.strip() if request.name else None,
        repository_url=request.repository_url.strip() if request.repository_url else None,
        linear_project_id=request.linear_project_id,
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectResponse(
        id=project["id"],
        user_id=project["user_id"],
        linear_project_id=project.get("linear_project_id"),
        name=project["name"],
        repository_url=project["repository_url"],
        local_path=project.get("local_path"),
        created_at=project["created_at"].isoformat() if project.get("created_at") else "",
        updated_at=project["updated_at"].isoformat() if project.get("updated_at") else "",
    )


@app.delete("/api/v1/projects/{project_id}")
async def delete_project_endpoint(
    project_id: str,
    auth_token: str | None = Cookie(default=None),
):
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not (user := await get_current_user(token=auth_token)):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    await delete_project(project_id=project_id, user_id=user.id)
    return {"message": "Project deleted successfully"}
