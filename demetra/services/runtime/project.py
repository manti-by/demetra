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

from demetra.library.models import Project
from demetra.services.persistence.database import get_connection
from demetra.services.runtime.constants import PG_RESERVED_WORDS
from demetra.services.runtime.subprocess import run_command
from demetra.settings import DB_USER, GIT, UV, WORKTREE_PATH


logger = logging.getLogger(__name__)


def quote_ident(ident: str) -> str:
    """Quote an identifier for use in PostgreSQL DDL statements.

    PostgreSQL does not support bind parameters for identifiers (DDL objects
    like roles, databases), so identifiers must be safely quoted inline.

    Args:
        ident: The identifier to quote.

    Returns:
        str: The double-quoted identifier with internal quotes escaped.
    """
    return '"' + ident.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    """Escape a string literal for inline use in PostgreSQL statements.

    Args:
        value: The string value to escape.

    Returns:
        str: The single-quoted literal with quotes doubled.
    """
    return "'" + value.replace("'", "''") + "'"


GITHUB_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def get_project_name(project: dict[str, Any]) -> str:
    """Generate a stable slug name for a project from its repository and id.

    Args:
        project: The project row as a dict.

    Returns:
        str: The slugified project name with underscores.
    """
    return slugify(f"{project['repository_name']}-{project['id'][:8]}").replace("-", "_")


def parse_github_url(url: str) -> tuple[str, str] | None:
    """Parse a GitHub repository URL into owner and repo names.

    Supports HTTPS, SSH and plain github.com path formats.

    Args:
        url: The repository URL to parse.

    Returns:
        tuple[str, str] | None: The owner and repository name, or None when
            the URL is not a recognized GitHub URL.

    Raises:
        ValueError: When a recognized GitHub URL has an unsafe segment.
    """
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
    """Clone the project repository into the worktree directory if needed.

    Returns the existing path when the checkout already exists.

    Args:
        project: The project row as a dict.

    Returns:
        Path: The local checkout path.

    Raises:
        ValueError: When the resolved path escapes the worktree root.
    """
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
        project_id=project["id"],
    )

    return project_path


async def setup_project_venv(project: Project) -> Path:
    """Bootstrap a per-project UV virtualenv inside the project checkout.

    Creates ``<local_path>/.venv`` with ``uv venv --seed`` on first use and
    reuses it on subsequent runs. The venv path is exposed to subprocesses by
    setting ``VIRTUAL_ENV`` and ``UV_PROJECT_ENVIRONMENT`` on the cached
    project environment, which the OS env allowlist forwards.

    Args:
        project: The project to set up the venv for.

    Returns:
        Path: The venv directory.

    Raises:
        RuntimeError: When the local path is missing or the venv bootstrap fails.
    """
    if not project.local_path:
        raise RuntimeError("Project local path is not set")

    local_path = Path(project.local_path)
    venv_path = local_path / ".venv"

    if not venv_path.exists():
        logger.info(f"Bootstrapping UV venv for {project.name} at {venv_path}")
        exit_code, _, stderr = await run_command(
            command=[str(UV["path"]), "venv", "--seed", str(venv_path)],
            target_path=local_path,
            project_id=project.id,
        )
        if exit_code != 0:
            # A failed bootstrap may leave a partial .venv behind; remove it so
            # the next run retries instead of treating the broken venv as valid.
            shutil.rmtree(venv_path, ignore_errors=True)
            raise RuntimeError(f"Failed to create UV venv at {venv_path}: {stderr.strip() or 'unknown error'}")

    env = dict(project.environment)
    env["VIRTUAL_ENV"] = str(venv_path)
    env["UV_PROJECT_ENVIRONMENT"] = str(venv_path)
    env["UV_PATH"] = str(UV["path"])
    # Prepend the venv bin directory to PATH so bare commands such as
    # ``python`` resolve executables from the project venv instead of the host.
    venv_bin = venv_path / "bin"
    current_path = env.get("PATH") or os.environ.get("PATH", "")
    env["PATH"] = f"{venv_bin}:{current_path}" if current_path else str(venv_bin)
    project.environment = env
    return venv_path


async def create_postgres_role_and_database(project: dict[str, Any]) -> tuple[str, str, str]:
    """Provision a PostgreSQL role and database for a project.

    Creates the role and database only when they do not already exist; the
    role is granted to the configured DB user.

    Args:
        project: The project row as a dict.

    Returns:
        tuple[str, str, str]: The database name, role name and password.

    Raises:
        ValueError: When the generated name conflicts with a reserved word or
            does not start with a letter.
    """
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
    """Provision all resources needed for a project to run.

    Clones the repository and creates the PostgreSQL role and database.

    Args:
        project: The project row as a dict.

    Returns:
        dict: The local path and database credentials.
    """
    local_path = await setup_project_directory(project=project)
    db_name, db_user, db_password = await create_postgres_role_and_database(project=project)
    return {"local_path": str(local_path), "db_name": db_name, "db_user": db_user, "db_password": db_password}


async def cleanup_project_resources(project: dict[str, Any]) -> None:
    """Drop the project's database, role and local checkout.

    Failures are logged but do not propagate so cleanup can continue.

    Args:
        project: The project row as a dict.
    """
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
    """Check whether any label matches 'epic' (case-insensitive).

    Args:
        labels: The list of label names.

    Returns:
        bool: True when an epic label is present.
    """
    return any(label.lower() == EPIC_LABEL for label in labels)


# Matches MAJOR.MINOR.PATCH with optional PEP 440 pre-release / build suffix.
_VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(.*)$")


def bump_project_version(target_path: Path, is_epic: bool = False) -> str | None:
    """Bump the ``[project]`` version in pyproject.toml and write it back.

    Epic changes bump the major version; other changes bump the minor version.
    The file is rewritten atomically via a temp file.

    Args:
        target_path: Directory containing ``pyproject.toml``.
        is_epic: Whether this is an epic change (major version bump).

    Returns:
        str | None: The new version string, or None when the version could
            not be read or bumped.
    """
    try:
        pyproject_file = target_path / "pyproject.toml"
        content = pyproject_file.read_text(encoding="utf-8")
        data = tomllib.loads(content)
    except FileNotFoundError:
        logger.warning(f"The configuration file was not found at {target_path}")
        return None
    except PermissionError:
        logger.warning("You do not have permission to read pyproject.toml")
        return None
    except tomllib.TOMLDecodeError as e:
        logger.warning(f"Invalid TOML syntax - {e}")
        return None

    try:
        current_version = data["project"]["version"]
    except KeyError:
        logger.warning("Project version not found in pyproject.toml")
        return None

    match = _VERSION_PATTERN.match(current_version)
    if not match:
        logger.warning(f"Invalid version format: {current_version!r}")
        return None

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
        logger.warning("Project section not found in pyproject.toml")
        return None

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
        logger.warning("Project version field not found in [project] section")
        return None

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
    """Return the index of the line containing a TOML section header.

    Args:
        lines: The file lines.
        target: The section header to find, e.g. ``"[project]"``.

    Returns:
        int | None: The index of the matching header, or None.
    """
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        # Match lines like [project], [project]  # comment, etc.
        if stripped.startswith("[") and "]" in stripped:
            header = stripped.split("]")[0] + "]"
            if header == target:
                return i
    return None


def _find_next_section_start(lines: list[str], start: int) -> int | None:
    """Return the index of the next TOML section header at or after a line.

    Args:
        lines: The file lines.
        start: The line index to begin searching from.

    Returns:
        int | None: The index of the next header, or None.
    """
    for i in range(start, len(lines)):
        stripped = lines[i].lstrip()
        if stripped.startswith("[") and "]" in stripped:
            return i
    return None
