import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
from slugify import slugify

from demetra.settings import (
    DB_HOST,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    HOME_PATH,
)


logger = logging.getLogger(__name__)

PROJECTS_BASE_PATH = HOME_PATH / ".demetra" / "projects"


def parse_github_url(url: str) -> tuple[str, str] | None:
    patterns = [
        r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?$",
    ]

    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            return match.group(1), match.group(2).replace(".git", "")

    parsed = urlparse(url)
    if parsed.netloc == "github.com" or parsed.netloc == "www.github.com":
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[0], parts[1].replace(".git", "")

    return None


async def setup_project_directory(repository_url: str, project_name: str) -> Path:
    parsed = parse_github_url(repository_url)
    if not parsed:
        raise ValueError(f"Invalid GitHub repository URL: {repository_url}")

    owner, repo = parsed
    project_path = PROJECTS_BASE_PATH / owner / repo
    project_path.parent.mkdir(parents=True, exist_ok=True)

    if project_path.exists():
        logger.info(f"Project directory already exists: {project_path}")
        return project_path

    from demetra.services.subprocess import run_command
    from demetra.settings import GIT

    logger.info(f"Cloning repository {repository_url} to {project_path}")
    await run_command(
        command=[str(GIT["path"]), "clone", repository_url, str(project_path)],
        target_path=project_path.parent,
    )

    return project_path


PG_RESERVED_WORDS = {
    "select",
    "insert",
    "update",
    "delete",
    "create",
    "drop",
    "alter",
    "table",
    "index",
    "view",
    "schema",
    "database",
    "role",
    "user",
    "group",
    "grant",
    "revoke",
    "join",
    "from",
    "where",
    "order",
    "by",
    "having",
    "limit",
    "offset",
    "union",
    "all",
    "distinct",
    "and",
    "or",
    "not",
    "null",
    "in",
    "between",
    "like",
    "exists",
    "case",
    "when",
    "then",
    "else",
    "end",
}


async def create_postgres_role_and_database(project_name: str) -> tuple[str, str, str]:
    slugified_name = slugify(project_name).replace("-", "_")
    if not slugified_name or not slugified_name[0].isalpha():
        raise ValueError(f"Invalid project name: {project_name}")
    if slugified_name.lower() in PG_RESERVED_WORDS:
        raise ValueError(f"Project name cannot be a PostgreSQL reserved word: {project_name}")

    password = slugify(f"{project_name}-password").replace("-", "_")

    conn = await asyncpg.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database="postgres",
    )

    try:
        role_exists = await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", slugified_name)
        if not role_exists:
            await conn.execute(
                f"CREATE ROLE {slugified_name} WITH LOGIN PASSWORD $1",
                password,
            )
            logger.info(f"Created role: {slugified_name}")

        db_exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", slugified_name)
        if not db_exists:
            await conn.execute(
                f"CREATE DATABASE {slugified_name} OWNER {slugified_name}",
            )
            logger.info(f"Created database: {slugified_name}")

        await conn.execute(f"ALTER ROLE {slugified_name} CREATEDB")
        logger.info(f"Granted CREATEDB to role: {slugified_name}")

    finally:
        await conn.close()

    return slugified_name, slugified_name, password


async def setup_project(project_name: str, repository_url: str) -> dict:
    local_path = await setup_project_directory(repository_url, project_name)
    db_name, db_user, db_password = await create_postgres_role_and_database(project_name)

    return {
        "local_path": str(local_path),
        "db_name": db_name,
        "db_user": db_user,
        "db_password": db_password,
    }
