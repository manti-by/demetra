import logging
import os
import re
import shutil
import tempfile
import tomllib
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


def quote_ident(ident: str) -> str:
    """
    PostgreSQL doesn't support bind parameters for identifiers (DDL objects like roles, databases).
    """
    return '"' + ident.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    """
    Escape a string literal for PostgreSQL by doubling single quotes.
    """
    return "'" + value.replace("'", "''") + "'"


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
    q_role = quote_ident(ident=role_name)
    q_password = quote_literal(value=password)

    async with get_connection() as connection:
        result = await connection.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role_name"),
            {"role_name": role_name},
        )
        if not result.fetchone():
            await connection.execute(
                text(f"CREATE ROLE {q_role} WITH LOGIN PASSWORD {q_password} CREATEDB"),
            )
            logger.info(f"Created role: {role_name}")
        await connection.commit()

    async with get_connection() as connection:
        result = await connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
            {"db_name": db_name},
        )
        if not result.fetchone():
            q_user = quote_ident(ident=DB_USER)
            q_db = quote_ident(ident=db_name)
            await connection.execute(
                text(f"GRANT {q_role} TO {q_user}"),
            )
            await connection.execute(
                text(f"CREATE DATABASE {q_db} OWNER {q_role}"),
            )
            logger.info(f"Created database: {db_name}")
        await connection.commit()

    return db_name, role_name, password


async def setup_project(project: dict[str, Any]) -> dict:
    local_path = await setup_project_directory(project=project)
    db_name, db_user, db_password = await create_postgres_role_and_database(project=project)
    return {"local_path": str(local_path), "db_name": db_name, "db_user": db_user, "db_password": db_password}


async def cleanup_project_resources(project: dict[str, Any]) -> None:
    project_name = get_project_name(project=project)
    role_name = db_name = project_name

    try:
        async with get_connection() as connection:
            result = await connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": db_name},
            )
            if result.fetchone():
                q_db = quote_ident(ident=db_name)
                await connection.execute(text(f"DROP DATABASE IF EXISTS {q_db}"))
                logger.info(f"Dropped database: {db_name}")
            await connection.commit()

        async with get_connection() as connection:
            result = await connection.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname = :role_name"),
                {"role_name": role_name},
            )
            if result.fetchone():
                q_role = quote_ident(ident=role_name)
                await connection.execute(text(f"DROP ROLE IF EXISTS {q_role}"))
                logger.info(f"Dropped role: {role_name}")
            await connection.commit()

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


EPIC_LABEL = "epic"


def is_epic_label(labels: list[str]) -> bool:
    """Check if any label matches 'epic' (case-insensitive)."""
    return any(label.lower() == EPIC_LABEL for label in labels)


# Matches MAJOR.MINOR.PATCH with optional PEP 440 pre-release / build suffix.
_VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(.*)$")


def bump_project_version(target_path: Path, is_epic: bool = False) -> str:
    """Read pyproject.toml, bump the version under [project], and write back."""
    pyproject_file = target_path / "pyproject.toml"
    content = pyproject_file.read_text(encoding="utf-8")

    data = tomllib.loads(content)
    try:
        current_version = data["project"]["version"]
    except KeyError:
        msg = "Project version not found in pyproject.toml"
        raise ValueError(msg) from None

    match = _VERSION_PATTERN.match(current_version)
    if not match:
        msg = f"Invalid version format: {current_version!r}"
        raise ValueError(msg)

    major = int(match.group(1))
    minor = int(match.group(2))
    suffix = match.group(4)  # PEP 440 suffix, empty for plain semver

    if is_epic:
        new_version = f"{major + 1}.0.0{suffix}"
    else:
        new_version = f"{major}.{minor + 1}.0{suffix}"

    lines = content.splitlines(keepends=True)
    project_start = _find_section_start(lines, "[project]")
    if project_start is None:
        msg = "Project section not found in pyproject.toml"
        raise ValueError(msg)

    project_end = _find_next_section_start(lines, project_start + 1)
    if project_end is None:
        project_end = len(lines)

    # Extract the [project] section body, apply regex, then splice it back.
    project_lines = lines[project_start:project_end]
    project_text = "".join(project_lines)

    new_project_text, count = re.subn(
        r'^(\s*version\s*=\s*)(["\'])([^"\']+)(["\'])(.*)',
        rf"\g<1>\g<2>{new_version}\g<2>\g<5>",
        project_text,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        msg = "Project version field not found in [project] section"
        raise ValueError(msg)

    lines[project_start:project_end] = [new_project_text]

    # Atomic write via temp file + rename.
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=pyproject_file.parent,
        delete=False,
    ) as tmp:
        tmp.write("".join(lines))
        tmp_path = tmp.name
    os.replace(tmp_path, pyproject_file)

    return new_version


def _find_section_start(lines: list[str], target: str) -> int | None:
    """Return the index of the line matching *target* section header."""
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        # Match lines like [project], [project]  # comment, etc.
        if stripped.startswith("[") and "]" in stripped:
            header = stripped.split("]")[0] + "]"
            if header == target:
                return i
    return None


def _find_next_section_start(lines: list[str], start: int) -> int | None:
    """Return the index of the next TOML section header at or after *start*."""
    for i in range(start, len(lines)):
        stripped = lines[i].lstrip()
        if stripped.startswith("[") and "]" in stripped:
            return i
    return None
