import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
from slugify import slugify
from sqlalchemy import text

from demetra.services.database import get_connection
from demetra.settings import DB_HOST, DB_PASSWORD, DB_PORT, DB_USER, WORKTREE_PATH


logger = logging.getLogger(__name__)


GITHUB_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


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


async def setup_project_directory(
    project_id: str,
    project_name: str,
    repository_url: str,
) -> Path:
    parsed = parse_github_url(repository_url)
    if not parsed:
        raise ValueError(f"Invalid GitHub repository URL: {repository_url}")

    owner, repo = parsed
    slugified_project_name = slugify(f"{repo}-{project_id[:8]}").replace("-", "_")
    project_path = WORKTREE_PATH / owner / slugified_project_name

    resolved_base = WORKTREE_PATH.resolve()
    resolved_path = project_path.resolve()
    if not str(resolved_path).startswith(str(resolved_base) + "/"):
        raise ValueError(f"Path traversal detected: {project_path} is outside {WORKTREE_PATH}")

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


async def create_postgres_role_and_database(project_id: str) -> tuple[str, str, str]:
    import secrets

    db_name = f"p_{project_id.replace('-', '')[:22]}"
    if db_name.lower() in PG_RESERVED_WORDS:
        raise ValueError("Generated database name conflicts with PostgreSQL reserved word")
    if not db_name[0].isalpha():
        raise ValueError(f"Invalid generated database name: {db_name}")

    password = secrets.token_urlsafe(32)
    role_name = db_name

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


async def setup_project(project_id: str, project_name: str, repository_url: str) -> dict:
    local_path = await setup_project_directory(
        project_id=project_id, project_name=project_name, repository_url=repository_url
    )
    db_name, db_user, db_password = await create_postgres_role_and_database(project_id=project_id)
    return {
        "local_path": str(local_path),
        "db_name": db_name,
        "db_user": db_user,
        "db_password": db_password,
    }


async def cleanup_project_resources(project_name: str, repository_url: str, project_id: str) -> None:
    db_name = f"p_{project_id.replace('-', '')[:22]}"

    try:
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database="postgres",
        )
        try:
            db_exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
            if db_exists:
                await conn.execute(f"DROP DATABASE IF EXISTS {db_name}")
                logger.info(f"Dropped database: {db_name}")

            role_exists = await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", db_name)
            if role_exists:
                await conn.execute(f"DROP ROLE IF EXISTS {db_name}")
                logger.info(f"Dropped role: {db_name}")
        finally:
            await conn.close()
    except Exception as e:
        logger.exception("Failed to cleanup PostgreSQL resources: %s", e)

    try:
        parsed = parse_github_url(repository_url)
        if parsed:
            owner, repo = parsed
            slugified_project_name = slugify(f"{repo}-{project_id[:8]}").replace("-", "_")
            project_path = WORKTREE_PATH / owner / slugified_project_name
            resolved_base = WORKTREE_PATH.resolve()
            resolved_path = project_path.resolve()
            if str(resolved_path).startswith(str(resolved_base) + "/") and project_path.exists():
                import shutil

                shutil.rmtree(project_path)
                logger.info(f"Removed project directory: {project_path}")
    except Exception as e:
        logger.exception("Failed to cleanup project directory: %s", e)
