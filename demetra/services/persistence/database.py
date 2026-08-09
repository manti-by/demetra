import asyncio
import logging
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine, delete, func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from demetra.library.models import Session, SessionHistory, TokenUsage
from demetra.library.tables import (
    allowlist_entries,
    jwt_tokens,
    oauth_tokens,
    project_environments,
    projects,
    session_history,
    sessions,
    users,
)
from demetra.settings import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


logger = logging.getLogger(__name__)


_engine_cache: dict[tuple[int, str], AsyncEngine] = {}
_cache_lock = threading.Lock()


def get_async_engine(db_name: str | None = None, echo: bool = False) -> AsyncEngine:
    """Create an async SQLAlchemy engine for the given database.

    Uses asyncpg over PostgreSQL with autocommit isolation and connection
    pinging.

    Args:
        db_name: Optional database name; defaults to the configured DB_NAME.
        echo: Whether to log SQL statements.

    Returns:
        AsyncEngine: The configured async engine.
    """
    database = db_name if db_name else DB_NAME
    url = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{database}"
    return create_async_engine(
        url,
        echo=echo,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )


def get_async_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session maker bound to the given engine.

    Args:
        engine: The async engine to bind.

    Returns:
        async_sessionmaker[AsyncSession]: A factory for AsyncSession objects.
    """
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session(
    engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession]:
    """Yield a database session as an async context manager.

    Args:
        engine: The async engine to create the session from.

    Yields:
        AsyncSession: An open async session.
    """
    async_session_maker = get_async_session_maker(engine)
    async with async_session_maker() as session:
        yield session


def get_sync_engine(db_name: str | None = None, echo: bool = False):
    """Create a synchronous SQLAlchemy engine for the given database.

    Uses psycopg over PostgreSQL.

    Args:
        db_name: Optional database name; defaults to the configured DB_NAME.
        echo: Whether to log SQL statements.

    Returns:
        Engine: The configured sync engine.
    """
    database = db_name if db_name else DB_NAME
    url = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{database}"
    return create_engine(url, echo=echo)


async def get_cached_engine(db_name: str | None = None) -> AsyncEngine:
    """Return a per-event-loop cached async engine, creating it on first use.

    Engines are cached keyed by the running event loop and database name.

    Args:
        db_name: Optional database name; defaults to the configured DB_NAME.

    Returns:
        AsyncEngine: The cached async engine.
    """
    loop_id = id(asyncio.get_running_loop())
    key = (loop_id, db_name or "default")
    if key not in _engine_cache:
        with _cache_lock:
            if key not in _engine_cache:
                _engine_cache[key] = get_async_engine(db_name=db_name)
    return _engine_cache[key]


@asynccontextmanager
async def get_connection(db_name: str | None = None) -> AsyncGenerator[AsyncSession]:
    """Yield a session from the cached engine as an async context manager.

    Args:
        db_name: Optional database name; defaults to the configured DB_NAME.

    Yields:
        AsyncSession: An open async session.
    """
    engine = await get_cached_engine(db_name)
    async_session_maker = get_async_session_maker(engine)
    async with async_session_maker() as session:
        yield session


@asynccontextmanager
async def get_transaction(db_name: str | None = None) -> AsyncGenerator[AsyncSession]:
    """Yield a session running inside an explicitly opened transaction.

    The application engine runs at ``AUTOCOMMIT`` isolation, where
    ``session.begin()`` is a no-op and every statement commits immediately.
    This manager issues the transaction control itself (``BEGIN`` /
    ``COMMIT`` / ``ROLLBACK``), so the yielded block runs atomically.

    Args:
        db_name: Optional database name; defaults to the configured DB_NAME.

    Yields:
        AsyncSession: A session inside an open transaction.
    """
    async with get_connection(db_name=db_name) as connection:
        await connection.execute(text("BEGIN"))
        try:
            yield connection
        except BaseException:
            await connection.execute(text("ROLLBACK"))
            raise
        else:
            await connection.execute(text("COMMIT"))


async def init_db() -> None:
    """Verify database connectivity with a trivial query."""
    async with get_connection() as connection:
        await connection.execute(text("SELECT 1"))


async def upsert_pending_session(
    task_id: str,
    session_id: str | None,
    project_id: str | None = None,
    user_id: str | None = None,
    name: str | None = None,
    linear_link: str | None = None,
) -> Session:
    """Create or update a pending session row for a task.

    Inserts a session in the ``initial`` step or, on conflict, refreshes the
    mutable fields while preserving the existing step.

    Args:
        task_id: The Linear task identifier.
        session_id: The opencode session id, or None while still pending.
        project_id: Optional project id the session belongs to.
        user_id: Optional user id the session belongs to.
        name: Optional display name for the session.
        linear_link: Optional link to the Linear issue.

    Returns:
        Session: The created or updated session record.

    Raises:
        BaseException: When the database returns no row.
    """
    now = datetime.now(UTC)
    async with get_connection() as connection:
        result = await connection.execute(
            text(
                """
                INSERT INTO sessions (task_id, name, session_id, build_plan, posted_to_linear, step, project_id, user_id, run_attempts, listener_attempts, pr_link, linear_link, created_at, updated_at)
                VALUES (:task_id, :name, :session_id, :build_plan, :posted_to_linear, :step, :project_id, :user_id, :run_attempts, :listener_attempts, :pr_link, :linear_link, :created_at, :updated_at)
                ON CONFLICT (task_id) DO UPDATE SET
                    name = COALESCE(NULLIF(EXCLUDED.name, ''), sessions.name),
                    session_id = COALESCE(NULLIF(EXCLUDED.session_id, ''), sessions.session_id),
                    step = sessions.step,
                    project_id = COALESCE(EXCLUDED.project_id, sessions.project_id),
                    user_id = COALESCE(EXCLUDED.user_id, sessions.user_id),
                    linear_link = COALESCE(EXCLUDED.linear_link, sessions.linear_link),
                    updated_at = EXCLUDED.updated_at
                RETURNING task_id, name, session_id, build_plan, posted_to_linear, step, project_id, user_id, run_attempts, listener_attempts, pr_link, linear_link, created_at, updated_at
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
                "listener_attempts": 0,
                "pr_link": None,
                "linear_link": linear_link,
                "created_at": now,
                "updated_at": now,
            },
        )
        row = result.fetchone()
        await connection.commit()

    if row is None:
        raise BaseException

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
        listener_attempts=row.listener_attempts,
        pr_link=row.pr_link,
        linear_link=row.linear_link,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


async def increment_run_attempts(task_id: str) -> int:
    """Increment the run attempt counter for a session.

    Args:
        task_id: The Linear task identifier.

    Returns:
        int: The updated run attempt count, or 0 when the session is missing.
    """
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


async def reset_listener_attempts(task_id: str) -> int:
    """Reset the listener attempt counter for a session to zero.

    Args:
        task_id: The Linear task identifier.

    Returns:
        int: The reset listener attempt count, or 0 when the session is missing.
    """
    async with get_connection() as connection:
        result = await connection.execute(
            text(
                """
                UPDATE sessions
                SET listener_attempts = 0, updated_at = :updated_at
                WHERE task_id = :task_id
                RETURNING listener_attempts
                """
            ),
            {
                "task_id": task_id,
                "updated_at": datetime.now(UTC),
            },
        )
        await connection.commit()
        row = result.fetchone()
    return row.listener_attempts if row else 0


async def increment_listener_attempts(task_id: str) -> int:
    """Increment the listener attempt counter for a session.

    Args:
        task_id: The Linear task identifier.

    Returns:
        int: The updated listener attempt count, or 0 when the session is
            missing.
    """
    async with get_connection() as connection:
        result = await connection.execute(
            text(
                """
                UPDATE sessions
                SET listener_attempts = listener_attempts + 1, updated_at = :updated_at
                WHERE task_id = :task_id
                RETURNING listener_attempts
                """
            ),
            {
                "task_id": task_id,
                "updated_at": datetime.now(UTC),
            },
        )
        await connection.commit()
        row = result.fetchone()
    return row.listener_attempts if row else 0


async def create_session(task_id: str, session_id: str) -> Session:
    """Create a pending session row linking a task to an opencode session.

    Args:
        task_id: The Linear task identifier.
        session_id: The opencode session id.

    Returns:
        Session: The created session record.
    """
    return await upsert_pending_session(task_id=task_id, session_id=session_id)


async def get_session(task_id: str) -> Session | None:
    """Fetch the session record for a task, if it exists.

    Args:
        task_id: The Linear task identifier.

    Returns:
        Session | None: The session record, or None when not found.
    """
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
        listener_attempts=row.listener_attempts,
        pr_link=row.pr_link,
        linear_link=row.linear_link,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


async def get_session_by_pr_link(pr_link: str) -> Session | None:
    """Fetch the session record associated with a pull request link.

    Args:
        pr_link: The PR link to look up.

    Returns:
        Session | None: The session record, or None when not found.
    """
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
        listener_attempts=row.listener_attempts,
        pr_link=row.pr_link,
        linear_link=row.linear_link,
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
    """Persist a session with its build plan, advancing the step to ``plan``.

    Upserts the session row by task id and returns the resulting record.

    Args:
        task_id: The Linear task identifier.
        build_plan: The build plan markdown to store.
        name: Optional display name for the session.
        session_id: Optional opencode session id.
        linear_link: Optional link to the Linear issue.

    Returns:
        Session: The saved session record.
    """
    now = datetime.now(UTC)
    async with get_connection() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO sessions (task_id, name, session_id, build_plan, posted_to_linear, step, project_id, user_id, run_attempts, listener_attempts, pr_link, linear_link, created_at, updated_at)
                VALUES (:task_id, :name, :session_id, :build_plan, :posted_to_linear, :step, :project_id, :user_id, :run_attempts, :listener_attempts, :pr_link, :linear_link, :created_at, :updated_at)
                ON CONFLICT (task_id) DO UPDATE SET
                    name = COALESCE(NULLIF(EXCLUDED.name, ''), sessions.name),
                    session_id = COALESCE(NULLIF(EXCLUDED.session_id, ''), sessions.session_id),
                    build_plan = EXCLUDED.build_plan,
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
                "session_id": session_id if session_id else "",
                "build_plan": build_plan,
                "posted_to_linear": False,
                "step": "plan",
                "project_id": None,
                "user_id": None,
                "run_attempts": 0,
                "listener_attempts": 0,
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
            listener_attempts=row.listener_attempts,
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
        listener_attempts=0,
        pr_link=None,
        linear_link=linear_link,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )


async def mark_session_posted(task_id: str) -> None:
    """Mark a session's build plan as posted to Linear.

    Args:
        task_id: The Linear task identifier.
    """
    now = datetime.now(UTC)
    async with get_connection() as connection:
        await connection.execute(
            sessions.update().where(sessions.c.task_id == task_id).values(posted_to_linear=True, updated_at=now)
        )
        await connection.commit()


async def update_session_pr_link(task_id: str, pr_link: str) -> None:
    """Record the pull request link on a session.

    Args:
        task_id: The Linear task identifier.
        pr_link: The PR link to store.
    """
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
    """Record the Linear issue link on a session.

    Args:
        task_id: The Linear task identifier.
        linear_link: The Linear issue link to store.
    """
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


async def get_sessions(user_id: str, step: str | None = None) -> list[dict]:
    """List sessions for a user, optionally filtered by current step.

    Sessions are returned newest first.

    Args:
        user_id: The user id to scope the query to.
        step: Optional step name to filter on.

    Returns:
        list[dict]: The matching session rows.
    """
    query = select(sessions).where(sessions.c.user_id == user_id)
    if step is not None:
        query = query.where(sessions.c.step == step)

    query = query.order_by(sessions.c.created_at.desc())

    async with get_connection() as connection:
        result = await connection.execute(query)
        rows = result.fetchall()

    return [dict(row._mapping) for row in rows]


async def save_oauth_token(service: str, access_token: str, refresh_token: str | None, expires_in: int) -> None:
    """Store or refresh an OAuth access token for a service.

    Args:
        service: The service identifier, e.g. ``"linear"``.
        access_token: The access token to store.
        refresh_token: Optional refresh token for the service.
        expires_in: Token lifetime in seconds from now.
    """
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
    """Return a non-expired stored OAuth token for a service.

    Args:
        service: The service identifier.

    Returns:
        tuple[str, str] | None: The access token and its expiry timestamp, or
            None when absent or expired.
    """
    async with get_connection() as connection:
        result = await connection.execute(select(oauth_tokens).where(oauth_tokens.c.service == service))
        row = result.fetchone()

    if not row:
        return None

    expires_at = row.expires_at.timestamp()
    if datetime.now(UTC).timestamp() < expires_at:
        return row.access_token, str(expires_at)


async def update_session_step(task_id: str, step: str) -> None:
    """Update the current workflow step of a session.

    Args:
        task_id: The Linear task identifier.
        step: The new step value.
    """
    async with get_connection() as connection:
        await connection.execute(
            sessions.update().where(sessions.c.task_id == task_id).values(step=step, updated_at=datetime.now(UTC))
        )
        await connection.commit()


async def get_session_step_name(task_id: str, user_id: str | None = None) -> tuple[str, str] | None:
    """Return the current step and name of a session, optionally user-scoped.

    Args:
        task_id: The Linear task identifier.
        user_id: Optional user id to scope the query to.

    Returns:
        tuple[str, str] | None: The step and name, or None when the session
            does not exist.
    """
    query = select(sessions.c.step, sessions.c.name).where(sessions.c.task_id == task_id)
    if user_id is not None:
        query = query.where(sessions.c.user_id == user_id)
    async with get_connection() as connection:
        result = await connection.execute(query)
        row = result.fetchone()
    if not row:
        return None
    return row.step or "initial", row.name or ""


async def record_session_history(
    session_id: str,
    step: str,
    length: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    reasoning_tokens: int | None = None,
    cache_read_tokens: int | None = None,
    cache_write_tokens: int | None = None,
    context_tokens: int | None = None,
    model: str | None = None,
) -> SessionHistory:
    """Record an opencode session's token usage at a workflow step.

    Args:
        session_id: The opencode session id.
        step: The workflow step name.
        length: Optional message length in characters.
        input_tokens: Optional input token count.
        output_tokens: Optional output token count.
        reasoning_tokens: Optional reasoning token count.
        cache_read_tokens: Optional cache read token count.
        cache_write_tokens: Optional cache write token count.
        context_tokens: Optional context window token count.
        model: Optional model identifier.

    Returns:
        SessionHistory: The persisted history record.
    """
    history_id = str(uuid4())
    now = datetime.now(UTC)
    async with get_connection() as connection:
        await connection.execute(
            insert(session_history).values(
                id=history_id,
                session_id=session_id,
                step=step,
                length=length,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                reasoning_tokens=reasoning_tokens,
                cache_read_tokens=cache_read_tokens,
                cache_write_tokens=cache_write_tokens,
                context_tokens=context_tokens,
                model=model,
                created_at=now,
            )
        )
        await connection.commit()

    return SessionHistory(
        id=history_id,
        session_id=session_id,
        step=step,
        length=length,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        context_tokens=context_tokens,
        model=model,
        created_at=now.isoformat(),
    )


async def get_session_id_by_task_id(task_id: str, user_id: str | None = None) -> str | None:
    """Return the opencode session id for a task, optionally user-scoped.

    Args:
        task_id: The Linear task identifier.
        user_id: Optional user id to scope the query to.

    Returns:
        str | None: The opencode session id, or None when not set.
    """
    query = select(sessions.c.session_id).where(sessions.c.task_id == task_id)
    if user_id is not None:
        query = query.where(sessions.c.user_id == user_id)
    async with get_connection() as connection:
        result = await connection.execute(query)
        row = result.fetchone()
    if not row or not row.session_id:
        return None
    return row.session_id


async def get_session_history(session_id: str) -> list[SessionHistory]:
    """Return all history rows for an opencode session in creation order.

    Args:
        session_id: The opencode session id.

    Returns:
        list[SessionHistory]: The history records for the session.
    """
    async with get_connection() as connection:
        result = await connection.execute(
            select(session_history)
            .where(session_history.c.session_id == session_id)
            .order_by(session_history.c.created_at)
        )
        rows = result.fetchall()

    return [
        SessionHistory(
            id=row.id,
            session_id=row.session_id,
            step=row.step,
            length=row.length,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            reasoning_tokens=row.reasoning_tokens,
            cache_read_tokens=row.cache_read_tokens,
            cache_write_tokens=row.cache_write_tokens,
            context_tokens=row.context_tokens,
            model=row.model,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


async def get_pending_session_task_ids() -> set[str]:
    """Return task ids of sessions that still lack an opencode session id.

    Returns:
        set[str]: The task ids of pending sessions.
    """
    async with get_connection() as connection:
        result = await connection.execute(select(sessions.c.task_id).where(sessions.c.session_id == ""))
        rows = result.fetchall()
    return {row.task_id for row in rows}


async def create_user(
    *,
    email: str,
    github_id: str | None = None,
    github_username: str | None = None,
    avatar_url: str | None = None,
    password_hash: str | None = None,
) -> str:
    """Create a new user record and return its id.

    Args:
        email: The user's email address.
        github_id: Optional GitHub account id.
        github_username: Optional GitHub username.
        avatar_url: Optional avatar image URL.
        password_hash: Optional password hash for password auth.

    Returns:
        str: The id of the created user.
    """
    user_id = str(uuid4())
    now = datetime.now(UTC)
    async with get_connection() as connection:
        await connection.execute(
            insert(users).values(
                id=user_id,
                github_id=github_id,
                github_username=github_username,
                email=email,
                password_hash=password_hash,
                avatar_url=avatar_url,
                role="user",
                created_at=now,
            )
        )
        await connection.commit()
    return user_id


async def get_user_by_github_id(github_id: str) -> dict | None:
    """Fetch a user by GitHub account id.

    Args:
        github_id: The GitHub account id.

    Returns:
        dict | None: The user row, or None when not found.
    """
    async with get_connection() as connection:
        result = await connection.execute(select(users).where(users.c.github_id == github_id))
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def get_user_by_email(email: str) -> dict | None:
    """Fetch a user by email address.

    Args:
        email: The user's email address.

    Returns:
        dict | None: The user row, or None when not found.
    """
    async with get_connection() as connection:
        result = await connection.execute(select(users).where(users.c.email == email))
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def get_user_by_id(user_id: str) -> dict | None:
    """Fetch a user by its internal id.

    Args:
        user_id: The user id.

    Returns:
        dict | None: The user row, or None when not found.
    """
    async with get_connection() as connection:
        result = await connection.execute(select(users).where(users.c.id == user_id))
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def get_user_by_github_username(github_username: str) -> dict | None:
    """Fetch a user by its GitHub username (login).

    Args:
        github_username: The GitHub username.

    Returns:
        dict | None: The user row, or None when not found.
    """
    async with get_connection() as connection:
        result = await connection.execute(select(users).where(users.c.github_username == github_username))
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def find_allowlist_entry(entry_type: str, value: str) -> dict | None:
    """Fetch an allowlist entry by its type and normalized value.

    Args:
        entry_type: The entry type, ``"email"`` or ``"github_username"``.
        value: The normalized entry value.

    Returns:
        dict | None: The entry row, or None when not found.
    """
    async with get_connection() as connection:
        result = await connection.execute(
            select(allowlist_entries).where(
                (allowlist_entries.c.entry_type == entry_type) & (allowlist_entries.c.value == value)
            )
        )
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def insert_allowlist_entry(entry_type: str, value: str, note: str | None, added_by: str | None) -> str:
    """Create a new allowlist entry and return its id.

    Args:
        entry_type: The entry type, ``"email"`` or ``"github_username"``.
        value: The normalized entry value.
        note: Optional operational note.
        added_by: Optional user id who added the entry, or None for system seed.

    Returns:
        str: The id of the created entry.
    """
    entry_id = str(uuid4())
    now = datetime.now(UTC)
    async with get_connection() as connection:
        await connection.execute(
            insert(allowlist_entries).values(
                id=entry_id,
                entry_type=entry_type,
                value=value,
                note=note,
                added_by=added_by,
                created_at=now,
                updated_at=now,
            )
        )
        await connection.commit()
    return entry_id


async def delete_allowlist_entry(entry_type: str, value: str) -> bool:
    """Delete an allowlist entry by its type and value.

    Args:
        entry_type: The entry type, ``"email"`` or ``"github_username"``.
        value: The normalized entry value.

    Returns:
        bool: True when a row was deleted, False when none matched.
    """
    async with get_connection() as connection:
        result = await connection.execute(
            delete(allowlist_entries)
            .where((allowlist_entries.c.entry_type == entry_type) & (allowlist_entries.c.value == value))
            .returning(allowlist_entries.c.id)
        )
        row = result.fetchone()
        await connection.commit()
    return row is not None


async def list_allowlist_entries() -> list[dict]:
    """List all allowlist entries, ordered by type then value.

    Returns:
        list[dict]: The allowlist entry rows.
    """
    async with get_connection() as connection:
        result = await connection.execute(
            select(allowlist_entries).order_by(allowlist_entries.c.entry_type, allowlist_entries.c.value)
        )
        rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


async def list_user_allowlist_seed_rows() -> list[dict]:
    """Return one allowlist seed row per user email and GitHub username field.

    Each current user yields an ``email`` row and a ``github_username`` row.
    A missing field is represented with a ``None`` ``value`` so the seeding
    routine can count it as skipped.

    Returns:
        list[dict]: Mappings of ``entry_type``, ``value`` and ``source_user_id``
            for every current user.
    """
    async with get_connection() as connection:
        result = await connection.execute(select(users.c.id, users.c.email, users.c.github_username))
        rows = result.fetchall()

    seed_rows: list[dict] = []
    for row in rows:
        seed_rows.append({"entry_type": "email", "value": row.email, "source_user_id": row.id})
        seed_rows.append({"entry_type": "github_username", "value": row.github_username, "source_user_id": row.id})
    return seed_rows


async def save_jwt_token(token: str, user_id: str, expires_at: str) -> None:
    """Persist a JWT session record for a user.

    The stored ``password_version`` is read from the user row at issuance, so
    any token minted before a password reset carries the old version and is
    rejected by :func:`verify_jwt_token` after the reset commits.

    Args:
        token: The JWT to store.
        user_id: The user id the token belongs to.
        expires_at: ISO-8601 expiry timestamp.

    Raises:
        RuntimeError: When no user row exists for the id.
    """
    now = datetime.now(UTC)
    expires_at_dt = datetime.fromisoformat(expires_at)

    async with get_connection() as connection:
        version_result = await connection.execute(
            text("SELECT password_version FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        )
        version_row = version_result.fetchone()
        if version_row is None:
            raise RuntimeError(f"User {user_id} not found while saving JWT session")

        await connection.execute(
            text(
                """
                INSERT INTO jwt_tokens (token, user_id, expires_at, created_at, password_version)
                VALUES (:token, :user_id, :expires_at, :created_at, :password_version)
                ON CONFLICT (token) DO NOTHING
                """
            ),
            {
                "token": token,
                "user_id": user_id,
                "expires_at": expires_at_dt,
                "created_at": now,
                "password_version": version_row[0],
            },
        )
        await connection.commit()


async def get_jwt_token(token: str) -> dict | None:
    """Fetch a stored JWT session record.

    Args:
        token: The JWT to look up.

    Returns:
        dict | None: The token row, or None when not found.
    """
    async with get_connection() as connection:
        result = await connection.execute(select(jwt_tokens).where(jwt_tokens.c.token == token))
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def get_user_jwt_tokens(user_id: str) -> list[dict]:
    """Fetch all stored JWT session records for a user.

    Args:
        user_id: The user id the tokens belong to.

    Returns:
        list[dict]: The token rows for the user.
    """
    async with get_connection() as connection:
        result = await connection.execute(select(jwt_tokens).where(jwt_tokens.c.user_id == user_id))
        rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


async def delete_jwt_token(token: str, connection: AsyncSession | None = None) -> None:
    """Delete a stored JWT session record, revoking the token.

    Args:
        token: The JWT to revoke.
        connection: An optional shared connection to run within; when omitted
            a new connection is opened and the change is committed.
    """
    statement = delete(jwt_tokens).where(jwt_tokens.c.token == token)
    if connection is None:
        async with get_connection() as conn:
            await conn.execute(statement)
            await conn.commit()
        return
    await connection.execute(statement)


async def update_user_keys(user_id: str, keys: dict) -> None:
    """Encrypt and store the API keys for a user.

    Args:
        user_id: The user id.
        keys: The API keys to encrypt and persist.
    """
    from demetra.services.persistence.encryption import encrypt

    encrypted_keys = encrypt(keys)
    async with get_connection() as connection:
        await connection.execute(users.update().where(users.c.id == user_id).values(keys=encrypted_keys))
        await connection.commit()


async def update_user_password(
    user_id: str,
    password_hash: str,
    connection: AsyncSession | None = None,
) -> None:
    """Replace the stored password hash for a user, invalidating prior sessions.

    Bumps ``password_version`` so every JWT minted before the change is
    rejected by :func:`verify_jwt_token`.

    Args:
        user_id: The user id.
        password_hash: The new password hash.
        connection: An optional shared connection to run within; when omitted
            a new connection is opened and the change is committed.
    """
    statement = (
        users.update()
        .where(users.c.id == user_id)
        .values(password_hash=password_hash, password_version=users.c.password_version + 1)
    )
    if connection is None:
        async with get_connection() as conn:
            await conn.execute(statement)
            await conn.commit()
        return
    await connection.execute(statement)


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
    """Create a project record and return its row as a dict.

    Args:
        user_id: The owning user id.
        name: The project display name.
        repository_url: The repository clone URL.
        repository_owner: The repository owner.
        repository_name: The repository name.
        linear_project_id: Optional linked Linear project id.
        local_path: Optional local checkout path.
        state: Initial project state, defaulting to ``"provisioning"``.

    Returns:
        dict: The created project row.
    """
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
    """Search projects by an exact, case-insensitive name match.

    Args:
        name: The project name to search for.

    Returns:
        list[dict]: The matching project rows.
    """
    async with get_connection() as connection:
        result = await connection.execute(select(projects).where(func.lower(projects.c.name) == name.lower()))
        rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


async def get_projects_by_user(user_id: str) -> list[dict]:
    """List all projects owned by a user.

    Args:
        user_id: The owning user id.

    Returns:
        list[dict]: The project rows for the user.
    """
    async with get_connection() as connection:
        result = await connection.execute(select(projects).where(projects.c.user_id == user_id))
        rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


async def get_project_by_id_system(project_id: str) -> dict | None:
    """Fetch a project by id without user scoping (system access).

    Args:
        project_id: The project id.

    Returns:
        dict | None: The project row, or None when not found.
    """
    async with get_connection() as connection:
        result = await connection.execute(select(projects).where(projects.c.id == project_id))
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def get_project_by_id(project_id: str, user_id: str) -> dict | None:
    """Fetch a project by id, scoped to a specific user.

    Args:
        project_id: The project id.
        user_id: The owning user id.

    Returns:
        dict | None: The project row, or None when not found.
    """
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
    """Update mutable fields of a user-scoped project.

    Only non-None fields are updated; the record must belong to the given
    user.

    Args:
        project_id: The project id.
        user_id: The owning user id.
        linear_project_id: Optional new Linear project link.
        name: Optional new project name.
        repository_url: Optional new repository URL.
        local_path: Optional new local checkout path.
        state: Optional new project state.

    Returns:
        dict | None: The updated project row, or None when not found.
    """
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
    """Return the decrypted environment variables of a project.

    Encrypted values are decrypted on read; failures yield an empty value.

    Args:
        project_id: The project id.
        user_id: Optional user id for ownership verification.

    Returns:
        dict[str, str]: The environment as a key-value mapping.

    Raises:
        LookupError: When a user is given and the project is not owned by them.
    """
    from demetra.services.persistence.encryption import decrypt_str

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
    """List a project's environment entries, masking encrypted values.

    Args:
        project_id: The project id.
        user_id: The owning user id for verification.

    Returns:
        list[dict]: One entry per environment variable; encrypted values are
            replaced with a mask.

    Raises:
        LookupError: When the project is not owned by the user.
    """
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
    """Create or update a project environment variable.

    Encrypted values are encrypted before storage.

    Args:
        project_id: The project id.
        user_id: The owning user id for verification.
        key: The environment variable name.
        value: The environment variable value.
        env_type: ``"text"`` or ``"encrypted"``.

    Returns:
        dict: The created or updated entry with the value masked when
            encrypted.

    Raises:
        LookupError: When the project is not owned by the user.
        RuntimeError: When the database returns no row.
    """
    from uuid import uuid4

    from demetra.library.models import ENCRYPTED_VALUE_MASK

    if not await get_project_by_id(project_id=project_id, user_id=user_id):
        raise LookupError("Project not found")

    if env_type == "encrypted":
        from demetra.services.persistence.encryption import encrypt_str

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
    """Delete an environment variable from a project.

    Args:
        project_id: The project id.
        user_id: The owning user id for verification.
        key: The environment variable name to delete.

    Raises:
        LookupError: When the project is not owned by the user.
    """
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
    """Delete a user-scoped project together with its environment entries.

    Args:
        project_id: The project id.
        user_id: The owning user id.

    Returns:
        bool: True when the project was deleted, False when it did not exist.
    """
    async with get_transaction() as connection:
        existing = await connection.execute(
            select(projects.c.id).where((projects.c.id == project_id) & (projects.c.user_id == user_id))
        )
        if not existing.fetchone():
            return False
        await connection.execute(delete(project_environments).where(project_environments.c.project_id == project_id))
        await connection.execute(
            delete(projects).where((projects.c.id == project_id) & (projects.c.user_id == user_id))
        )
    return True


async def delete_session(task_id: str, user_id: str) -> bool:
    """Delete a user-scoped session and its log file.

    Args:
        task_id: The Linear task identifier.
        user_id: The owning user id.

    Returns:
        bool: True when the session existed and was deleted, otherwise False.
    """
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


async def record_session_step_history(
    session_id: str | None,
    step: str,
    usage: TokenUsage | None = None,
    model: str | None = None,
) -> SessionHistory | None:
    """Record a workflow step's token usage for a session, when a session exists.

    Args:
        session_id: The opencode session id, or None to skip recording.
        step: The workflow step name.
        usage: Optional token usage summary to persist.
        model: Optional model identifier.

    Returns:
        SessionHistory | None: The persisted history record, or None when no
            session id is given.
    """
    if not session_id:
        return None

    return await record_session_history(
        session_id=session_id,
        step=step,
        length=usage.total if usage is not None else None,
        input_tokens=usage.input if usage is not None else None,
        output_tokens=usage.output if usage is not None else None,
        reasoning_tokens=usage.reasoning if usage is not None else None,
        cache_read_tokens=usage.cache_read if usage is not None else None,
        cache_write_tokens=usage.cache_write if usage is not None else None,
        context_tokens=usage.context if usage is not None else None,
        model=model,
    )
