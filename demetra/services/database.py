import asyncio
import logging
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine, delete, func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from demetra.library.models import Session
from demetra.library.tables import jwt_tokens, oauth_tokens, project_environments, projects, sessions, users
from demetra.settings import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


logger = logging.getLogger(__name__)


_engine_cache: dict[tuple[int, str], AsyncEngine] = {}
_cache_lock = threading.Lock()


def get_async_engine(db_name: str | None = None, echo: bool = False) -> AsyncEngine:
    database = db_name if db_name else DB_NAME
    url = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{database}"
    return create_async_engine(
        url,
        echo=echo,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )


def get_async_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session(
    engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession]:
    async_session_maker = get_async_session_maker(engine)
    async with async_session_maker() as session:
        yield session


def get_sync_engine(db_name: str | None = None, echo: bool = False):
    database = db_name if db_name else DB_NAME
    url = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{database}"
    return create_engine(url, echo=echo)


async def get_cached_engine(db_name: str | None = None) -> AsyncEngine:
    loop_id = id(asyncio.get_running_loop())
    key = (loop_id, db_name or "default")
    if key not in _engine_cache:
        with _cache_lock:
            if key not in _engine_cache:
                _engine_cache[key] = get_async_engine(db_name=db_name)
    return _engine_cache[key]


@asynccontextmanager
async def get_connection(db_name: str | None = None) -> AsyncGenerator[AsyncSession]:
    engine = await get_cached_engine(db_name)
    async_session_maker = get_async_session_maker(engine)
    async with async_session_maker() as session:
        yield session


async def init_db() -> None:
    async with get_connection() as connection:
        await connection.execute(text("SELECT 1"))


async def upsert_pending_session(
    task_id: str,
    session_id: str | None,
    project_id: str | None = None,
    user_id: str | None = None,
    name: str | None = None,
) -> Session:
    now = datetime.now(UTC)
    async with get_connection() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO sessions (task_id, name, session_id, build_plan, posted_to_linear, step, project_id, user_id, run_attempts, pr_link, linear_link, created_at, updated_at)
                VALUES (:task_id, :name, :session_id, :build_plan, :posted_to_linear, :step, :project_id, :user_id, :run_attempts, :pr_link, :linear_link, :created_at, :updated_at)
                ON CONFLICT (task_id) DO UPDATE SET
                    name = COALESCE(NULLIF(EXCLUDED.name, ''), sessions.name),
                    session_id = COALESCE(NULLIF(EXCLUDED.session_id, ''), sessions.session_id),
                    step = EXCLUDED.step,
                    project_id = COALESCE(EXCLUDED.project_id, sessions.project_id),
                    user_id = COALESCE(EXCLUDED.user_id, sessions.user_id),
                    linear_link = COALESCE(EXCLUDED.linear_link, sessions.linear_link),
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "task_id": task_id,
                "name": name if name else "",
                "session_id": session_id if session_id is not None else "",
                "build_plan": "",
                "posted_to_linear": False,
                "step": "initial",
                "project_id": project_id,
                "user_id": user_id,
                "run_attempts": 0,
                "pr_link": None,
                "linear_link": None,
                "created_at": now,
                "updated_at": now,
            },
        )
        await connection.commit()

    return Session(
        task_id=task_id,
        name=name,
        session_id=session_id,
        build_plan="",
        posted_to_linear=False,
        step="initial",
        project_id=project_id,
        user_id=user_id,
        run_attempts=0,
        pr_link=None,
        linear_link=None,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )


async def increment_run_attempts(task_id: str) -> int:
    """Increment run_attempts for a session and return the new value."""
    async with get_connection() as connection:
        result = await connection.execute(
            text(
                """
                UPDATE sessions
                SET run_attempts = run_attempts + 1, updated_at = :updated_at
                WHERE task_id = :task_id
                RETURNING run_attempts
                """
            ),
            {
                "task_id": task_id,
                "updated_at": datetime.now(UTC),
            },
        )
        await connection.commit()
        row = result.fetchone()
    return row.run_attempts if row else 0


async def create_session(task_id: str, session_id: str) -> Session:
    return await upsert_pending_session(task_id=task_id, session_id=session_id)


async def get_session(task_id: str) -> Session | None:
    async with get_connection() as connection:
        result = await connection.execute(select(sessions).where(sessions.c.task_id == task_id))
        row = result.fetchone()

    if not row:
        return None

    return Session(
        task_id=row.task_id,
        name=row.name,
        session_id=row.session_id,
        build_plan=row.build_plan,
        posted_to_linear=bool(row.posted_to_linear),
        step=row.step or "initial",
        project_id=row.project_id,
        user_id=row.user_id,
        run_attempts=row.run_attempts,
        pr_link=row.pr_link,
        linear_link=row.linear_link,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


async def get_session_by_pr_link(pr_link: str) -> Session | None:
    async with get_connection() as connection:
        result = await connection.execute(select(sessions).where(sessions.c.pr_link == pr_link))
        row = result.fetchone()

    if not row:
        return None

    return Session(
        task_id=row.task_id,
        name=row.name,
        session_id=row.session_id,
        build_plan=row.build_plan,
        posted_to_linear=bool(row.posted_to_linear),
        step=row.step or "initial",
        project_id=row.project_id,
        user_id=row.user_id,
        run_attempts=row.run_attempts,
        pr_link=row.pr_link,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


async def save_session(
    task_id: str,
    build_plan: str,
    name: str | None = None,
    session_id: str | None = None,
    linear_link: str | None = None,
) -> Session:
    now = datetime.now(UTC)
    async with get_connection() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO sessions (task_id, name, session_id, build_plan, posted_to_linear, step, project_id, user_id, run_attempts, pr_link, linear_link, created_at, updated_at)
                VALUES (:task_id, :name, :session_id, :build_plan, :posted_to_linear, :step, :project_id, :user_id, :run_attempts, :pr_link, :linear_link, :created_at, :updated_at)
                ON CONFLICT (task_id) DO UPDATE SET
                    name = COALESCE(NULLIF(EXCLUDED.name, ''), sessions.name),
                    session_id = COALESCE(NULLIF(EXCLUDED.session_id, ''), sessions.session_id),
                    build_plan = EXCLUDED.build_plan,
                    step = COALESCE(EXCLUDED.step, sessions.step),
                    project_id = COALESCE(EXCLUDED.project_id, sessions.project_id),
                    user_id = COALESCE(EXCLUDED.user_id, sessions.user_id),
                    linear_link = COALESCE(EXCLUDED.linear_link, sessions.linear_link),
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "task_id": task_id,
                "name": name if name else "",
                "session_id": session_id if session_id else "",
                "build_plan": build_plan,
                "posted_to_linear": False,
                "step": "plan",
                "project_id": None,
                "user_id": None,
                "run_attempts": 0,
                "pr_link": None,
                "linear_link": linear_link,
                "created_at": now,
                "updated_at": now,
            },
        )
        await connection.commit()

        result = await connection.execute(select(sessions).where(sessions.c.task_id == task_id))
        row = result.fetchone()

    if row:
        return Session(
            task_id=row.task_id,
            name=row.name,
            session_id=row.session_id,
            build_plan=row.build_plan,
            posted_to_linear=bool(row.posted_to_linear),
            step=row.step or "initial",
            project_id=row.project_id,
            user_id=row.user_id,
            run_attempts=row.run_attempts,
            pr_link=row.pr_link,
            linear_link=row.linear_link,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
        )

    return Session(
        task_id=task_id,
        name=name,
        session_id=session_id,
        build_plan=build_plan,
        posted_to_linear=False,
        step="plan",
        project_id=None,
        user_id=None,
        run_attempts=0,
        pr_link=None,
        linear_link=linear_link,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )


async def mark_session_posted(task_id: str) -> None:
    now = datetime.now(UTC)
    async with get_connection() as connection:
        await connection.execute(
            sessions.update().where(sessions.c.task_id == task_id).values(posted_to_linear=True, updated_at=now)
        )
        await connection.commit()


async def update_session_pr_link(task_id: str, pr_link: str) -> None:
    now = datetime.now(UTC)
    async with get_connection() as connection:
        await connection.execute(
            text(
                """
                UPDATE sessions
                SET pr_link = :pr_link, updated_at = :updated_at
                WHERE task_id = :task_id
                """
            ),
            {
                "task_id": task_id,
                "pr_link": pr_link,
                "updated_at": now,
            },
        )
        await connection.commit()


async def update_session_linear_link(task_id: str, linear_link: str) -> None:
    now = datetime.now(UTC)
    async with get_connection() as connection:
        await connection.execute(
            text(
                """
                UPDATE sessions
                SET linear_link = :linear_link, updated_at = :updated_at
                WHERE task_id = :task_id
                """
            ),
            {
                "task_id": task_id,
                "linear_link": linear_link,
                "updated_at": now,
            },
        )
        await connection.commit()


async def get_sessions(user_id: str, status: str | None = None) -> list[dict]:
    query = select(sessions).where(sessions.c.user_id == user_id)
    if status:
        query = query.where(sessions.c.status == status)

    query = query.order_by(sessions.c.created_at.desc())

    async with get_connection() as connection:
        result = await connection.execute(query)
        rows = result.fetchall()

    return [dict(row._mapping) for row in rows]


async def save_oauth_token(service: str, access_token: str, refresh_token: str | None, expires_in: int) -> None:
    expires_at = datetime.fromtimestamp(datetime.now(UTC).timestamp() + expires_in, tz=UTC)
    async with get_connection() as connection:
        if refresh_token is not None:
            await connection.execute(
                text(
                    """
                    INSERT INTO oauth_tokens (service, access_token, refresh_token, expires_at)
                    VALUES (:service, :access_token, :refresh_token, :expires_at)
                    ON CONFLICT (service) DO UPDATE SET
                        access_token = EXCLUDED.access_token,
                        refresh_token = EXCLUDED.refresh_token,
                        expires_at = EXCLUDED.expires_at
                    """
                ),
                {
                    "service": service,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_at": expires_at,
                },
            )
        else:
            await connection.execute(
                text(
                    """
                    INSERT INTO oauth_tokens (service, access_token, expires_at)
                    VALUES (:service, :access_token, :expires_at)
                    ON CONFLICT (service) DO UPDATE SET
                        access_token = EXCLUDED.access_token,
                        expires_at = EXCLUDED.expires_at
                    """
                ),
                {
                    "service": service,
                    "access_token": access_token,
                    "expires_at": expires_at,
                },
            )
        await connection.commit()


async def get_oauth_token(service: str) -> tuple[str, str] | None:
    async with get_connection() as connection:
        result = await connection.execute(select(oauth_tokens).where(oauth_tokens.c.service == service))
        row = result.fetchone()

    if not row:
        return None

    expires_at = row.expires_at.timestamp()
    if datetime.now(UTC).timestamp() < expires_at:
        return row.access_token, str(expires_at)


async def update_session_step(task_id: str, step: str) -> None:
    async with get_connection() as connection:
        await connection.execute(
            sessions.update().where(sessions.c.task_id == task_id).values(step=step, updated_at=datetime.now(UTC))
        )
        await connection.commit()


async def get_pending_session_task_ids() -> set[str]:
    async with get_connection() as connection:
        result = await connection.execute(select(sessions.c.task_id).where(sessions.c.session_id == ""))
        rows = result.fetchall()
    return {row.task_id for row in rows}


async def create_user(github_id: str, github_username: str, email: str | None, avatar_url: str | None = None) -> str:
    user_id = str(uuid4())
    now = datetime.now(UTC)
    async with get_connection() as connection:
        await connection.execute(
            insert(users).values(
                id=user_id,
                github_id=github_id,
                github_username=github_username,
                email=email,
                avatar_url=avatar_url,
                role="user",
                created_at=now,
            )
        )
        await connection.commit()
    return user_id


async def get_user_by_github_id(github_id: str) -> dict | None:
    async with get_connection() as connection:
        result = await connection.execute(select(users).where(users.c.github_id == github_id))
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def get_user_by_id(user_id: str) -> dict | None:
    async with get_connection() as connection:
        result = await connection.execute(select(users).where(users.c.id == user_id))
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def save_jwt_token(token: str, user_id: str, expires_at: str) -> None:
    now = datetime.now(UTC)
    expires_at_dt = datetime.fromisoformat(expires_at)

    async with get_connection() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO jwt_tokens (token, user_id, expires_at, created_at)
                VALUES (:token, :user_id, :expires_at, :created_at)
                ON CONFLICT (token) DO NOTHING
                """
            ),
            {
                "token": token,
                "user_id": user_id,
                "expires_at": expires_at_dt,
                "created_at": now,
            },
        )
        await connection.commit()


async def get_jwt_token(token: str) -> dict | None:
    async with get_connection() as connection:
        result = await connection.execute(select(jwt_tokens).where(jwt_tokens.c.token == token))
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def delete_jwt_token(token: str) -> None:
    async with get_connection() as connection:
        await connection.execute(delete(jwt_tokens).where(jwt_tokens.c.token == token))
        await connection.commit()


async def update_user_keys(user_id: str, keys: dict) -> None:
    from demetra.services.encryption import encrypt

    encrypted_keys = encrypt(keys)
    async with get_connection() as connection:
        await connection.execute(users.update().where(users.c.id == user_id).values(keys=encrypted_keys))
        await connection.commit()


async def create_project(
    user_id: str,
    name: str,
    repository_url: str,
    repository_owner: str,
    repository_name: str,
    linear_project_id: str | None = None,
    local_path: str | None = None,
    state: str = "provisioning",
) -> dict:
    project_id = str(uuid4())
    now = datetime.now(UTC)

    async with get_connection() as connection:
        await connection.execute(
            insert(projects).values(
                id=project_id,
                user_id=user_id,
                linear_project_id=linear_project_id,
                name=name,
                repository_url=repository_url,
                repository_name=repository_name,
                repository_owner=repository_owner,
                local_path=local_path,
                state=state,
                created_at=now,
                updated_at=now,
            )
        )
        await connection.commit()

    return {
        "id": project_id,
        "user_id": user_id,
        "linear_project_id": linear_project_id,
        "name": name,
        "repository_url": repository_url,
        "repository_name": repository_name,
        "repository_owner": repository_owner,
        "local_path": local_path,
        "state": state,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


async def search_projects_by_name(name: str) -> list[dict]:
    async with get_connection() as connection:
        result = await connection.execute(select(projects).where(func.lower(projects.c.name) == name.lower()))
        rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


async def get_projects_by_user(user_id: str) -> list[dict]:
    async with get_connection() as connection:
        result = await connection.execute(select(projects).where(projects.c.user_id == user_id))
        rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


async def get_project_by_id_system(project_id: str) -> dict | None:
    async with get_connection() as connection:
        result = await connection.execute(select(projects).where(projects.c.id == project_id))
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def get_project_by_id(project_id: str, user_id: str) -> dict | None:
    async with get_connection() as connection:
        result = await connection.execute(
            select(projects).where(projects.c.id == project_id, projects.c.user_id == user_id)
        )
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def update_project(
    project_id: str,
    user_id: str,
    linear_project_id: str | None = None,
    name: str | None = None,
    repository_url: str | None = None,
    local_path: str | None = None,
    state: str | None = None,
) -> dict | None:
    now = datetime.now(UTC)
    update_values: dict[str, datetime | str] = {"updated_at": now}

    if linear_project_id is not None:
        update_values["linear_project_id"] = linear_project_id

    if name is not None:
        update_values["name"] = name

    if repository_url is not None:
        update_values["repository_url"] = repository_url

    if local_path is not None:
        update_values["local_path"] = local_path

    if state is not None:
        update_values["state"] = state

    async with get_connection() as connection:
        await connection.execute(
            projects.update()
            .where((projects.c.id == project_id) & (projects.c.user_id == user_id))
            .values(**update_values)
        )
        await connection.commit()

        result = await connection.execute(
            select(projects).where((projects.c.id == project_id) & (projects.c.user_id == user_id))
        )
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def get_project_environments(project_id: str, user_id: str | None = None) -> dict[str, str]:
    from demetra.services.encryption import decrypt_str

    if user_id and not await get_project_by_id(project_id=project_id, user_id=user_id):
        raise LookupError("Project not found")

    async with get_connection() as connection:
        result = await connection.execute(
            select(project_environments).where(project_environments.c.project_id == project_id)
        )
        rows = result.fetchall()

    env: dict[str, str] = {}
    for row in rows:
        if row.type == "encrypted":
            try:
                env[row.key] = decrypt_str(row.value)
            except ValueError:
                logger.exception("Failed to decrypt env var '%s' for project '%s'", row.key, project_id)
                env[row.key] = ""
        else:
            env[row.key] = row.value
    return env


async def list_project_environments(project_id: str, user_id: str) -> list[dict]:
    from demetra.library.models import ENCRYPTED_VALUE_MASK

    if not await get_project_by_id(project_id=project_id, user_id=user_id):
        raise LookupError("Project not found")

    async with get_connection() as connection:
        result = await connection.execute(
            select(project_environments).where(project_environments.c.project_id == project_id)
        )
        rows = result.fetchall()
    return [
        {
            "id": row.id,
            "project_id": row.project_id,
            "key": row.key,
            "value": ENCRYPTED_VALUE_MASK if row.type == "encrypted" else row.value,
            "type": row.type,
        }
        for row in rows
    ]


async def upsert_project_environment(
    project_id: str,
    user_id: str,
    key: str,
    value: str,
    env_type: str = "text",
) -> dict:
    from uuid import uuid4

    from demetra.library.models import ENCRYPTED_VALUE_MASK

    if not await get_project_by_id(project_id=project_id, user_id=user_id):
        raise LookupError("Project not found")

    if env_type == "encrypted":
        from demetra.services.encryption import encrypt_str

        stored_value = encrypt_str(value)
    else:
        stored_value = value

    async with get_connection() as connection:
        result = await connection.execute(
            text(
                """
                INSERT INTO project_environment (id, project_id, key, value, type)
                VALUES (:id, :project_id, :key, :value, :type)
                ON CONFLICT (project_id, key) DO UPDATE SET
                    value = EXCLUDED.value,
                    type = EXCLUDED.type
                RETURNING id, type
                """
            ),
            {
                "id": str(uuid4()),
                "project_id": project_id,
                "key": key,
                "value": stored_value,
                "type": env_type,
            },
        )
        await connection.commit()
        row = result.fetchone()

    if row is None:
        raise RuntimeError("Failed to insert project environment")

    return {
        "id": row.id,
        "project_id": project_id,
        "key": key,
        "value": ENCRYPTED_VALUE_MASK if env_type == "encrypted" else value,
        "type": row.type,
    }


async def delete_project_environment(project_id: str, user_id: str, key: str) -> None:
    if not await get_project_by_id(project_id=project_id, user_id=user_id):
        raise LookupError("Project not found")

    async with get_connection() as connection:
        await connection.execute(
            delete(project_environments).where(
                (project_environments.c.project_id == project_id) & (project_environments.c.key == key)
            )
        )
        await connection.commit()


async def delete_project(project_id: str, user_id: str) -> bool:
    async with get_connection() as connection:
        async with connection.begin():
            existing = await connection.execute(
                select(projects.c.id).where((projects.c.id == project_id) & (projects.c.user_id == user_id))
            )
            if not existing.fetchone():
                return False
            await connection.execute(
                delete(project_environments).where(project_environments.c.project_id == project_id)
            )
            await connection.execute(
                delete(projects).where((projects.c.id == project_id) & (projects.c.user_id == user_id))
            )
    return True


async def delete_session(task_id: str, user_id: str) -> bool:
    from demetra.settings import LOG_DIR

    async with get_connection() as connection:
        result = await connection.execute(
            delete(sessions)
            .where((sessions.c.task_id == task_id) & (sessions.c.user_id == user_id))
            .returning(sessions.c.task_id)
        )
        row = result.fetchone()
        await connection.commit()
        if not row:
            return False

    sessions_log_dir = (LOG_DIR / "sessions").resolve()
    log_path = (sessions_log_dir / f"{task_id}.log").resolve()
    try:
        log_path.relative_to(sessions_log_dir)
    except ValueError:
        return True

    if log_path.exists():
        try:
            log_path.unlink()
        except OSError:
            pass

    return True
