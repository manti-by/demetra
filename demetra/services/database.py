import asyncio
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from demetra.db import (
    get_async_engine,
    jwt_tokens,
    oauth_tokens,
    projects,
    sessions,
    users,
)
from demetra.library.models import Session


_engine_cache: dict[tuple[int, str], AsyncEngine] = {}
_cache_lock = threading.Lock()


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
    async with AsyncSession(engine) as session:
        yield session


async def init_db() -> None:
    from sqlalchemy import text

    async with get_connection() as conn:
        await conn.execute(text("SELECT 1"))


async def upsert_pending_session(
    task_id: str,
    session_id: str | None,
    project_id: str | None = None,
    user_id: str | None = None,
) -> Session:
    now = datetime.now(UTC)
    async with get_connection() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO sessions (task_id, session_id, build_plan, posted_to_linear, status, project_id, user_id, created_at, updated_at)
                VALUES (:task_id, :session_id, :build_plan, :posted_to_linear, :status, :project_id, :user_id, :created_at, :updated_at)
                ON CONFLICT (task_id) DO UPDATE SET
                    session_id = COALESCE(NULLIF(EXCLUDED.session_id, ''), sessions.session_id),
                    status = EXCLUDED.status,
                    project_id = COALESCE(EXCLUDED.project_id, sessions.project_id),
                    user_id = COALESCE(EXCLUDED.user_id, sessions.user_id),
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "task_id": task_id,
                "session_id": session_id if session_id is not None else "",
                "build_plan": "",
                "posted_to_linear": False,
                "status": "pending",
                "project_id": project_id,
                "user_id": user_id,
                "created_at": now,
                "updated_at": now,
            },
        )
        await conn.commit()
    return Session(
        task_id=task_id,
        session_id=session_id,
        build_plan="",
        posted_to_linear=False,
        status="pending",
        project_id=project_id,
        user_id=user_id,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )


async def create_session(task_id: str, session_id: str) -> Session:
    return await upsert_pending_session(task_id=task_id, session_id=session_id)


async def get_session(task_id: str) -> Session | None:
    async with get_connection() as conn:
        result = await conn.execute(select(sessions).where(sessions.c.task_id == task_id))
        row = result.fetchone()
    if row:
        return Session(
            task_id=row.task_id,
            session_id=row.session_id,
            build_plan=row.build_plan,
            posted_to_linear=bool(row.posted_to_linear),
            status=row.status or "pending",
            project_id=row.project_id,
            user_id=row.user_id,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
        )
    return None


async def save_session(task_id: str, session_id: str, build_plan: str) -> Session:
    now = datetime.now(UTC)
    async with get_connection() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO sessions (task_id, session_id, build_plan, posted_to_linear, status, project_id, user_id, created_at, updated_at)
                VALUES (:task_id, :session_id, :build_plan, :posted_to_linear, :status, :project_id, :user_id, :created_at, :updated_at)
                ON CONFLICT (task_id) DO UPDATE SET
                    session_id = COALESCE(NULLIF(EXCLUDED.session_id, ''), sessions.session_id),
                    build_plan = EXCLUDED.build_plan,
                    status = COALESCE(sessions.status, 'pending'),
                    project_id = COALESCE(EXCLUDED.project_id, sessions.project_id),
                    user_id = COALESCE(EXCLUDED.user_id, sessions.user_id),
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "task_id": task_id,
                "session_id": session_id,
                "build_plan": build_plan,
                "posted_to_linear": False,
                "status": "pending",
                "project_id": None,
                "user_id": None,
                "created_at": now,
                "updated_at": now,
            },
        )
        await conn.commit()

        result = await conn.execute(select(sessions).where(sessions.c.task_id == task_id))
        row = result.fetchone()

    if row:
        return Session(
            task_id=row.task_id,
            session_id=row.session_id,
            build_plan=row.build_plan,
            posted_to_linear=bool(row.posted_to_linear),
            status=row.status or "pending",
            project_id=row.project_id,
            user_id=row.user_id,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
        )
    return Session(
        task_id=task_id,
        session_id=session_id,
        build_plan=build_plan,
        posted_to_linear=False,
        status="pending",
        project_id=None,
        user_id=None,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )


async def mark_session_posted(task_id: str) -> None:
    now = datetime.now(UTC)
    async with get_connection() as conn:
        await conn.execute(
            sessions.update().where(sessions.c.task_id == task_id).values(posted_to_linear=True, updated_at=now)
        )
        await conn.commit()


async def get_sessions(user_id: str, status: str | None = None) -> list[dict]:
    async with get_connection() as conn:
        if status:
            result = await conn.execute(
                select(sessions)
                .where(sessions.c.user_id == user_id, sessions.c.status == status)
                .order_by(sessions.c.created_at.desc())
            )
        else:
            result = await conn.execute(
                select(sessions).where(sessions.c.user_id == user_id).order_by(sessions.c.created_at.desc())
            )
        rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


async def save_oauth_token(service: str, access_token: str, refresh_token: str | None, expires_in: int) -> None:
    expires_at = datetime.fromtimestamp(datetime.now(UTC).timestamp() + expires_in, tz=UTC)
    async with get_connection() as conn:
        if refresh_token is not None:
            await conn.execute(
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
            await conn.execute(
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
        await conn.commit()


async def get_oauth_token(service: str) -> tuple[str, str] | None:
    async with get_connection() as conn:
        result = await conn.execute(select(oauth_tokens).where(oauth_tokens.c.service == service))
        row = result.fetchone()
    if row:
        expires_at = row.expires_at.timestamp()
        if datetime.now(UTC).timestamp() < expires_at:
            return row.access_token, str(expires_at)
    return None


async def update_session_status(task_id: str, status: str) -> None:
    now = datetime.now(UTC)
    async with get_connection() as conn:
        await conn.execute(sessions.update().where(sessions.c.task_id == task_id).values(status=status, updated_at=now))
        await conn.commit()


async def get_pending_session_task_ids() -> set[str]:
    async with get_connection() as conn:
        result = await conn.execute(
            select(sessions.c.task_id).where(
                sessions.c.status.not_in(["processed", "failed"]),
                sessions.c.session_id == "",
            )
        )
        rows = result.fetchall()
    return {row.task_id for row in rows}


async def create_user(github_id: str, github_username: str, email: str | None) -> str:
    from uuid import uuid4

    user_id = str(uuid4())
    now = datetime.now(UTC)
    async with get_connection() as conn:
        await conn.execute(
            insert(users).values(
                id=user_id,
                github_id=github_id,
                github_username=github_username,
                email=email,
                role="user",
                created_at=now,
            )
        )
        await conn.commit()
    return user_id


async def get_user_by_github_id(github_id: str) -> dict | None:
    async with get_connection() as conn:
        result = await conn.execute(select(users).where(users.c.github_id == github_id))
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def get_user_by_id(user_id: str) -> dict | None:
    async with get_connection() as conn:
        result = await conn.execute(select(users).where(users.c.id == user_id))
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def save_jwt_token(token: str, user_id: str, expires_at: str) -> None:
    now = datetime.now(UTC)
    expires_at_dt = datetime.fromisoformat(expires_at)
    async with get_connection() as conn:
        await conn.execute(
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
        await conn.commit()


async def get_jwt_token(token: str) -> dict | None:
    async with get_connection() as conn:
        result = await conn.execute(select(jwt_tokens).where(jwt_tokens.c.token == token))
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def delete_jwt_token(token: str) -> None:
    async with get_connection() as conn:
        await conn.execute(delete(jwt_tokens).where(jwt_tokens.c.token == token))
        await conn.commit()


async def update_user_keys(user_id: str, keys: dict) -> None:
    from demetra.services.encryption import encrypt

    encrypted_keys = encrypt(keys)
    async with get_connection() as conn:
        await conn.execute(users.update().where(users.c.id == user_id).values(keys=encrypted_keys))
        await conn.commit()


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
    from uuid import uuid4

    project_id = str(uuid4())
    now = datetime.now(UTC)
    async with get_connection() as conn:
        await conn.execute(
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
        await conn.commit()
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


async def get_projects_by_user(user_id: str) -> list[dict]:
    async with get_connection() as conn:
        result = await conn.execute(select(projects).where(projects.c.user_id == user_id))
        rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


async def get_project_by_id(project_id: str, user_id: str) -> dict | None:
    async with get_connection() as conn:
        result = await conn.execute(select(projects).where(projects.c.id == project_id, projects.c.user_id == user_id))
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

    async with get_connection() as conn:
        await conn.execute(
            projects.update()
            .where((projects.c.id == project_id) & (projects.c.user_id == user_id))
            .values(**update_values)
        )
        await conn.commit()

        result = await conn.execute(
            select(projects).where((projects.c.id == project_id) & (projects.c.user_id == user_id))
        )
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def delete_project(project_id: str, user_id: str) -> None:
    async with get_connection() as conn:
        await conn.execute(projects.delete().where((projects.c.id == project_id) & (projects.c.user_id == user_id)))
        await conn.commit()
