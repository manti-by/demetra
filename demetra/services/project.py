import logging
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from slugify import slugify
from sqlalchemy import text

from demetra.services.constants import PG_RESERVED_WORDS
from demetra.services.database import get_connection
from demetra.services.subprocess import run_command
from demetra.settings import DB_USER, GIT, WORKTREE_PATH


logger = logging.getLogger(__name__)


GITHUB_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def get_project_name(project: dict[str, Any]) -> str:
    return slugify(f"{project['repository_name']}-{project['id'][:8]}").replace("-", "_")


def parse_github_url(url: str) -> tuple[str, str] | None:
    patterns = [
        r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?$",
    ]

    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            owner, repo = match.group(1), match.group(2).replace(".git", "")
            if not GITHUB_SEGMENT_PATTERN.match(owner):
                raise ValueError(f"Invalid GitHub owner segment: {owner}")
            if not GITHUB_SEGMENT_PATTERN.match(repo):
                raise ValueError(f"Invalid GitHub repository segment: {repo}")
            return owner, repo

    parsed = urlparse(url)
    if parsed.netloc == "github.com" or parsed.netloc == "www.github.com":
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1].replace(".git", "")
            if not GITHUB_SEGMENT_PATTERN.match(owner):
                raise ValueError(f"Invalid GitHub owner segment: {owner}")
            if not GITHUB_SEGMENT_PATTERN.match(repo):
                raise ValueError(f"Invalid GitHub repository segment: {repo}")
            return owner, repo

    return None


async def setup_project_directory(project: dict[str, Any]) -> Path:
    project_name = get_project_name(project=project)
    project_path = WORKTREE_PATH / project["repository_owner"] / project_name

    resolved_base = WORKTREE_PATH.resolve()
    resolved_path = project_path.resolve()
    if not str(resolved_path).startswith(str(resolved_base) + "/"):
        raise ValueError(f"Path traversal detected: {project_path} is outside {WORKTREE_PATH}")

    project_path.parent.mkdir(parents=True, exist_ok=True)

    if project_path.exists():
        logger.info(f"Project directory already exists: {project_path}")
        return project_path

    logger.info(f"Cloning repository {project['repository_url']} to {project_path}")
    await run_command(
        command=[str(GIT["path"]), "clone", project["repository_url"], str(project_path)],
        target_path=project_path.parent,
    )

    return project_path


async def create_postgres_role_and_database(project: dict[str, Any]) -> tuple[str, str, str]:
    project_name = get_project_name(project=project)
    if project_name.lower() in PG_RESERVED_WORDS:
        raise ValueError("Generated database name conflicts with PostgreSQL reserved word")
    if not project_name[0].isalpha():
        raise ValueError(f"Invalid generated database name: {project_name}")

    role_name = password = db_name = project_name

    async with get_connection() as session:
        result = await session.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role_name"),
            {"role_name": role_name},
        )
        if not result.fetchone():
            await session.execute(
                text(f"CREATE ROLE {role_name} WITH LOGIN PASSWORD '{password}' CREATEDB"),
            )
            logger.info(f"Created role: {role_name}")
        await session.commit()

    async with get_connection() as session:
        result = await session.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
            {"db_name": db_name},
        )
        if not result.fetchone():
            await session.execute(
                text(f"GRANT {role_name} TO {DB_USER}"),
            )
            await session.execute(
                text(f"CREATE DATABASE {db_name} OWNER {role_name}"),
            )
            logger.info(f"Created database: {db_name}")
        await session.commit()

    return db_name, role_name, password


async def setup_project(project: dict[str, Any]) -> dict:
    local_path = await setup_project_directory(project=project)
    db_name, db_user, db_password = await create_postgres_role_and_database(project=project)
    return {"local_path": str(local_path), "db_name": db_name, "db_user": db_user, "db_password": db_password}


async def cleanup_project_resources(project: dict[str, Any]) -> None:
    project_name = get_project_name(project=project)
    role_name = db_name = project_name

    try:
        async with get_connection() as session:
            result = await session.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": db_name},
            )
            if result.fetchone():
                await session.execute(
                    text(f"DROP DATABASE IF EXISTS {db_name}"),
                )
                logger.info(f"Dropped database: {db_name}")
            await session.commit()

        async with get_connection() as session:
            result = await session.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname = :role_name"),
                {"role_name": role_name},
            )
            if result.fetchone():
                await session.execute(
                    text(f"DROP ROLE IF EXISTS {role_name}"),
                )
                logger.info(f"Dropped role: {role_name}")
            await session.commit()

    except Exception as e:
        logger.exception(f"Failed to cleanup PostgreSQL resources: {e}", e)

    try:
        project_path = WORKTREE_PATH / project["repository_owner"] / project_name
        resolved_base = WORKTREE_PATH.resolve()
        resolved_path = project_path.resolve()
        if str(resolved_path).startswith(str(resolved_base) + "/") and project_path.exists():
            shutil.rmtree(project_path)
            logger.info(f"Removed project directory: {project_path}")

    except Exception as e:
        logger.exception(f"Failed to cleanup project directory: {e}")
