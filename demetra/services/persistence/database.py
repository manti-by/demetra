import asyncio
import logging
import re
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Column, create_engine, delete, func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from demetra.library.models import Session, SessionHistory, SessionState, TokenUsage, WaitlistEntryUpdate
from demetra.library.tables import (
    agent_sessions,
    allowlist_entries,
    jwt_tokens,
    oauth_tokens,
    project_environments,
    projects,
    session_history,
    sessions,
    users,
    waitlist_entries,
)
from demetra.settings import DATABASE


logger = logging.getLogger(__name__)


_engine_cache: dict[tuple[int, str], AsyncEngine] = {}
_cache_lock = threading.Lock()

SAFE_TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def get_async_engine(db_name: str | None = None, echo: bool = False) -> AsyncEngine:
    """Create an async SQLAlchemy engine for the given database.

    Uses asyncpg over PostgreSQL with autocommit isolation and connection
    pinging.

    Args:
        db_name: Optional database name; defaults to the configured
            ``DATABASE["name"]``.
        echo: Whether to log SQL statements.

    Returns:
        AsyncEngine: The configured async engine.
    """
    database = db_name if db_name else DATABASE["name"]
    url = f"postgresql+asyncpg://{DATABASE['user']}:{DATABASE['password']}@{DATABASE['host']}:{DATABASE['port']}/{database}"
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
        db_name: Optional database name; defaults to the configured
            ``DATABASE["name"]``.
        echo: Whether to log SQL statements.

    Returns:
        Engine: The configured sync engine.
    """
    database = db_name if db_name else DATABASE["name"]
    url = f"postgresql+psycopg://{DATABASE['user']}:{DATABASE['password']}@{DATABASE['host']}:{DATABASE['port']}/{database}"
    return create_engine(url, echo=echo)


async def get_cached_engine(db_name: str | None = None) -> AsyncEngine:
    """Return a per-event-loop cached async engine, creating it on first use.

    Engines are cached keyed by the running event loop and database name.

    Args:
        db_name: Optional database name; defaults to the configured
            ``DATABASE["name"]``.

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
        db_name: Optional database name; defaults to the configured
            ``DATABASE["name"]``.

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
        db_name: Optional database name; defaults to the configured
            ``DATABASE["name"]``.

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
                RETURNING task_id, name, session_id, build_plan, posted_to_linear, step, is_research, project_id, user_id, run_attempts, listener_attempts, pr_link, linear_link, research_report, created_at, updated_at
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
        is_research=bool(row.is_research),
        project_id=row.project_id,
        user_id=row.user_id,
        run_attempts=row.run_attempts,
        listener_attempts=row.listener_attempts,
        pr_link=row.pr_link,
        linear_link=row.linear_link,
        research_report=row.research_report,
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
        is_research=bool(row.is_research),
        project_id=row.project_id,
        user_id=row.user_id,
        run_attempts=row.run_attempts,
        listener_attempts=row.listener_attempts,
        pr_link=row.pr_link,
        linear_link=row.linear_link,
        research_report=row.research_report,
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
        is_research=bool(row.is_research),
        project_id=row.project_id,
        user_id=row.user_id,
        run_attempts=row.run_attempts,
        listener_attempts=row.listener_attempts,
        pr_link=row.pr_link,
        linear_link=row.linear_link,
        research_report=row.research_report,
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
            is_research=bool(row.is_research),
            project_id=row.project_id,
            user_id=row.user_id,
            run_attempts=row.run_attempts,
            listener_attempts=row.listener_attempts,
            pr_link=row.pr_link,
            linear_link=row.linear_link,
            research_report=row.research_report,
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
        is_research=False,
        project_id=None,
        user_id=None,
        run_attempts=0,
        listener_attempts=0,
        pr_link=None,
        linear_link=linear_link,
        research_report=None,
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


async def update_session_research_report(task_id: str, research_report: str) -> bool:
    """Record the research report on a session.

    Args:
        task_id: The Linear task identifier.
        research_report: The research report markdown to store.

    Returns:
        bool: True when a row was updated, False when no session matched.
    """
    now = datetime.now(UTC)
    async with get_connection() as connection:
        result = await connection.execute(
            text(
                """
                UPDATE sessions
                SET research_report = :research_report, updated_at = :updated_at
                WHERE task_id = :task_id
                """
            ),
            {
                "task_id": task_id,
                "research_report": research_report,
                "updated_at": now,
            },
        )
        await connection.commit()
        return getattr(result, "rowcount", 0) > 0


async def get_sessions(user_id: str, step: str | None = None) -> list[dict]:
    """List sessions for a user, optionally filtered by current step.

    Sessions are returned newest first. Each row carries a ``has_history`` flag
    derived from ``session_history`` (resolved by ``task_id``) so the UI can
    offer the history view without depending on the display-only
    ``sessions.session_id`` pointer.

    Args:
        user_id: The user id to scope the query to.
        step: Optional step name to filter on.

    Returns:
        list[dict]: The matching session rows, each with a ``has_history`` flag.
    """
    has_history = (
        select(session_history.c.id)
        .where(session_history.c.task_id == sessions.c.task_id)
        .exists()
        .label("has_history")
    )
    query = select(sessions, has_history).where(sessions.c.user_id == user_id)
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


async def update_session_step(*, task_id: str, step: str) -> None:
    """Update the current workflow step of a session.

    This only advances the step; history rows are recorded separately, either
    through :func:`record_session_step` for non-agent steps or through
    :func:`record_agent_invocation` for agent steps. Keeping the two apart is
    what avoids the empty step rows that used to shadow the invocation rows.

    Args:
        task_id: The Linear task identifier.
        step: The new step value.
    """
    now = datetime.now(UTC)
    async with get_connection() as connection:
        await connection.execute(
            sessions.update().where(sessions.c.task_id == task_id).values(step=step, updated_at=now)
        )
        await connection.commit()


async def record_session_step(task_id: str, step: str) -> SessionHistory:
    """Record a non-agent workflow step as a ``kind='step'`` history row.

    The row is upserted per ``(task_id, step)`` so a step recorded from two
    paths (e.g. ``awaiting_input`` is set both when the plan moves the ticket
    and again by the cleanup path) produces exactly one row instead of the
    empty/populated duplicates that used to shadow agent rows.

    Args:
        task_id: The Linear task identifier.
        step: The workflow step name.

    Returns:
        SessionHistory: The persisted history record.
    """
    now = datetime.now(UTC)
    async with get_connection() as connection:
        existing = await connection.execute(
            select(session_history.c.id).where(
                (session_history.c.task_id == task_id)
                & (session_history.c.step == step)
                & (session_history.c.kind == "step")
            )
        )
        row = existing.fetchone()
        if row is not None:
            return SessionHistory(
                id=row.id, session_id=None, task_id=task_id, kind="step", step=step, created_at=now.isoformat()
            )

        history_id = str(uuid4())
        await connection.execute(
            insert(session_history).values(
                id=history_id,
                task_id=task_id,
                kind="step",
                step=step,
                created_at=now,
            )
        )
        await connection.commit()

    return SessionHistory(
        id=history_id, session_id=None, task_id=task_id, kind="step", step=step, created_at=now.isoformat()
    )


async def record_agent_invocation(
    *,
    task_id: str,
    step: str,
    session_id: str,
    usage: TokenUsage | None = None,
    agent: str | None = None,
    model: str | None = None,
    cost: float | None = None,
    outcome: str | None = None,
    fork_of: str | None = None,
    is_primary: bool = False,
) -> SessionHistory:
    """Record one agent invocation, attributing an exact token delta to it.

    ``agent_sessions`` keeps one row per ``(task_id, session_id)`` and holds the
    cumulative cursor last observed from ``info.tokens``; the delta
    ``max(0, cumulative - cursor)`` is added to a ``kind='invocation'``
    ``session_history`` row upserted per ``(task_id, session_id, step)``. The
    delta is *accumulated* onto the row, not replaced, because build iterations
    share one ``(session, step)`` row and each contributes only its own
    increment; re-capturing the same invocation is a no-op since its delta is
    then 0. A ``None`` ``usage`` (a failed export) records attribution without
    advancing the cursor or clearing previously recorded tokens. The cursor is
    never seeded from a fork parent: a fork's ``info.tokens`` restarts, so its
    first delta is its own cumulative total.

    Args:
        task_id: The Linear task identifier.
        step: The workflow step name.
        session_id: The opencode session id.
        usage: The cumulative token usage from the export, or None.
        agent: The agent reported by ``info.agent``.
        model: The serialized model reported by ``info.model``.
        cost: The cumulative session cost reported by ``info.cost``.
        outcome: The session outcome reported by ``info.outcome``.
        fork_of: The parent session id when this session was forked, for
            lineage only — it never feeds the delta.
        is_primary: Whether this session becomes the task's primary session.

    Returns:
        SessionHistory: The persisted invocation history record.
    """
    now = datetime.now(UTC)
    history_id = str(uuid4())
    async with get_transaction() as connection:
        existing = await connection.execute(
            text(
                """
                SELECT id, cursor_input, cursor_output, cursor_reasoning, cursor_cache_read, cursor_cache_write, cursor_cost
                  FROM agent_sessions
                 WHERE task_id = :task_id AND session_id = :session_id
                """
            ),
            {"task_id": task_id, "session_id": session_id},
        )
        cursor = existing.fetchone()

        agent_session_id = cursor.id if cursor is not None else None
        delta: dict[str, int | None] = {
            "input_tokens": None,
            "output_tokens": None,
            "reasoning_tokens": None,
            "cache_read_tokens": None,
            "cache_write_tokens": None,
        }
        context_tokens: int | None = None
        delta_cost: float | None = None
        new_cursor: dict[str, int | float | None] = {
            "cursor_input": None,
            "cursor_output": None,
            "cursor_reasoning": None,
            "cursor_cache_read": None,
            "cursor_cache_write": None,
            "cursor_cost": None,
        }

        if usage is not None:
            previous = {
                "input_tokens": cursor.cursor_input if cursor is not None else None,
                "output_tokens": cursor.cursor_output if cursor is not None else None,
                "reasoning_tokens": cursor.cursor_reasoning if cursor is not None else None,
                "cache_read_tokens": cursor.cursor_cache_read if cursor is not None else None,
                "cache_write_tokens": cursor.cursor_cache_write if cursor is not None else None,
            }
            current = {
                "input_tokens": usage.input,
                "output_tokens": usage.output,
                "reasoning_tokens": usage.reasoning,
                "cache_read_tokens": usage.cache_read,
                "cache_write_tokens": usage.cache_write,
            }
            for field in delta:
                delta[field] = max(0, current[field] - (previous[field] or 0))
            context_tokens = usage.context
            new_cursor = {
                "cursor_input": usage.input,
                "cursor_output": usage.output,
                "cursor_reasoning": usage.reasoning,
                "cursor_cache_read": usage.cache_read,
                "cursor_cache_write": usage.cache_write,
                "cursor_cost": None,
            }
            if cost is not None:
                previous_cost = cursor.cursor_cost if cursor is not None else None
                delta_cost = max(0.0, cost - (previous_cost or 0.0))
                new_cursor["cursor_cost"] = cost

        is_new = agent_session_id is None
        if agent_session_id is None:
            agent_session_id = str(uuid4())

        # Clear the previous primary before writing this one: the partial unique
        # index on (task_id) WHERE is_primary rejects a second primary row, so
        # the insert/update must come after the demotion.
        if is_primary:
            await connection.execute(
                update(agent_sessions)
                .where((agent_sessions.c.task_id == task_id) & (agent_sessions.c.id != agent_session_id))
                .values(is_primary=False)
            )
            await connection.execute(
                update(sessions).where(sessions.c.task_id == task_id).values(session_id=session_id, updated_at=now)
            )

        if is_new:
            await connection.execute(
                insert(agent_sessions).values(
                    id=agent_session_id,
                    task_id=task_id,
                    session_id=session_id,
                    step=step,
                    agent=agent,
                    model=model,
                    fork_of=fork_of,
                    outcome=outcome,
                    is_primary=is_primary,
                    created_at=now,
                    updated_at=now,
                    **new_cursor,
                )
            )
        else:
            await connection.execute(
                update(agent_sessions)
                .where(agent_sessions.c.id == agent_session_id)
                .values(
                    step=step,
                    agent=agent if agent is not None else agent_sessions.c.agent,
                    model=model if model is not None else agent_sessions.c.model,
                    fork_of=fork_of if fork_of is not None else agent_sessions.c.fork_of,
                    outcome=outcome if outcome is not None else agent_sessions.c.outcome,
                    is_primary=is_primary if is_primary else agent_sessions.c.is_primary,
                    updated_at=now,
                    **{
                        field: (value if value is not None else getattr(agent_sessions.c, field))
                        for field, value in new_cursor.items()
                    },
                )
            )

        length = None
        if usage is not None:
            length = sum(value or 0 for value in delta.values())

        existing_row = await connection.execute(
            text(
                """
                SELECT id, input_tokens, output_tokens, reasoning_tokens,
                       cache_read_tokens, cache_write_tokens, context_tokens, cost, length
                  FROM session_history
                 WHERE task_id = :task_id AND session_id = :session_id AND step = :step AND kind = 'invocation'
                 LIMIT 1
                """
            ),
            {"task_id": task_id, "session_id": session_id, "step": step},
        )
        row = existing_row.fetchone()

        if row is not None:
            history_id = row.id
            # Accumulate onto the existing row: build iterations share one
            # (session, step) row and the cursor has already advanced, so each
            # invocation contributes only its own delta. Re-capturing the same
            # invocation is a no-op because its delta is then 0. context_tokens
            # is a snapshot, so it is overwritten rather than summed.
            accumulated: dict[str, int | None] = {
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "reasoning_tokens": row.reasoning_tokens,
                "cache_read_tokens": row.cache_read_tokens,
                "cache_write_tokens": row.cache_write_tokens,
            }
            row_length = row.length
            row_cost = row.cost
            if usage is not None:
                for field in accumulated:
                    accumulated[field] = (accumulated[field] or 0) + (delta[field] or 0)
                row_length = (row_length or 0) + (length or 0)
            if delta_cost is not None:
                row_cost = (row_cost or 0.0) + delta_cost
            row_context = context_tokens if context_tokens is not None else row.context_tokens
            await connection.execute(
                update(session_history)
                .where(session_history.c.id == history_id)
                .values(
                    agent=agent if agent is not None else session_history.c.agent,
                    model=model if model is not None else session_history.c.model,
                    length=row_length,
                    context_tokens=row_context,
                    cost=row_cost,
                    **accumulated,
                )
            )
        else:
            await connection.execute(
                insert(session_history).values(
                    id=history_id,
                    task_id=task_id,
                    agent_session_id=agent_session_id,
                    session_id=session_id,
                    kind="invocation",
                    step=step,
                    length=length,
                    context_tokens=context_tokens,
                    cost=delta_cost,
                    agent=agent,
                    model=model,
                    created_at=now,
                    **delta,
                )
            )
            accumulated = dict(delta)
            row_length = length
            row_cost = delta_cost
            row_context = context_tokens

    return SessionHistory(
        id=history_id,
        session_id=session_id,
        task_id=task_id,
        agent_session_id=agent_session_id,
        kind="invocation",
        step=step,
        length=row_length,
        input_tokens=accumulated["input_tokens"],
        output_tokens=accumulated["output_tokens"],
        reasoning_tokens=accumulated["reasoning_tokens"],
        cache_read_tokens=accumulated["cache_read_tokens"],
        cache_write_tokens=accumulated["cache_write_tokens"],
        context_tokens=row_context,
        cost=row_cost,
        model=model,
        agent=agent,
        created_at=now.isoformat(),
    )


async def invalidate_agent_sessions(task_id: str) -> None:
    """Clear the primary marker for a task's agent sessions.

    Called after a worktree is removed so a superseded session is never resolved
    as the task's live primary. History still resolves by ``task_id``, so this
    never hides the session's history.

    Args:
        task_id: The Linear task identifier.
    """
    now = datetime.now(UTC)
    async with get_connection() as connection:
        await connection.execute(
            update(agent_sessions)
            .where((agent_sessions.c.task_id == task_id) & (agent_sessions.c.is_primary))
            .values(is_primary=False, updated_at=now)
        )
        await connection.commit()


async def get_session_state(task_id: str, user_id: str | None = None) -> SessionState | None:
    """Return the current step, name and flow of a session, optionally user-scoped.

    Args:
        task_id: The Linear task identifier.
        user_id: Optional user id to scope the query to.

    Returns:
        SessionState | None: The step, name and research flag, or None when the
            session does not exist.
    """
    query = select(sessions.c.step, sessions.c.name, sessions.c.is_research).where(sessions.c.task_id == task_id)
    if user_id is not None:
        query = query.where(sessions.c.user_id == user_id)
    async with get_connection() as connection:
        result = await connection.execute(query)
        row = result.fetchone()
    if not row:
        return None
    return SessionState(step=row.step or "initial", name=row.name or "", is_research=bool(row.is_research))


async def update_session_is_research(task_id: str, is_research: bool) -> None:
    """Update the research flow flag of a session.

    Args:
        task_id: The Linear task identifier.
        is_research: Whether the session runs the read-only research flow.
    """
    async with get_connection() as connection:
        await connection.execute(
            sessions.update()
            .where(sessions.c.task_id == task_id)
            .values(is_research=is_research, updated_at=datetime.now(UTC))
        )
        await connection.commit()


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


async def get_session_history(task_id: str) -> list[SessionHistory]:
    """Return all history rows for a task in recording order.

    History resolves by ``task_id`` rather than the opencode session id: a task
    can span several sessions (forks, restarts), and the display-only
    ``sessions.session_id`` pointer can be stale or absent. Ordering is by
    ``created_at`` then ``id`` so a step row and its invocation row keep a
    stable, insertion-consistent order.

    Args:
        task_id: The Linear task identifier.

    Returns:
        list[SessionHistory]: The history records for the task.
    """
    async with get_connection() as connection:
        result = await connection.execute(
            select(session_history)
            .where(session_history.c.task_id == task_id)
            .order_by(session_history.c.created_at, session_history.c.id)
        )
        rows = result.fetchall()

    return [
        SessionHistory(
            id=row.id,
            session_id=row.session_id,
            task_id=row.task_id,
            agent_session_id=row.agent_session_id,
            kind=row.kind,
            step=row.step,
            length=row.length,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            reasoning_tokens=row.reasoning_tokens,
            cache_read_tokens=row.cache_read_tokens,
            cache_write_tokens=row.cache_write_tokens,
            context_tokens=row.context_tokens,
            cost=row.cost,
            model=row.model,
            agent=row.agent,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


async def get_pending_session_task_ids() -> set[str]:
    """Return task ids of sessions that still lack an attributed agent session.

    A session is pending until an ``agent_sessions`` row exists for its
    ``task_id``; the display-only ``sessions.session_id`` pointer is no longer
    the source of truth for attribution.

    Returns:
        set[str]: The task ids of pending sessions.
    """
    has_agent_session = select(agent_sessions.c.id).where(agent_sessions.c.task_id == sessions.c.task_id).exists()
    async with get_connection() as connection:
        result = await connection.execute(select(sessions.c.task_id).where(~has_agent_session))
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


async def insert_allowlist_entry(
    entry_type: str, value: str, note: str | None, added_by: str | None, connection: AsyncSession | None = None
) -> str:
    """Create a new allowlist entry and return its id.

    Args:
        entry_type: The entry type, ``"email"`` or ``"github_username"``.
        value: The normalized entry value.
        note: Optional operational note (e.g. the GitHub email).
        added_by: Optional user id who added the entry, or None for system seed.
        connection: An optional shared connection to run within; when omitted
            a new connection is opened and the change is committed.

    Returns:
        str: The id of the created entry.
    """
    entry_id = str(uuid4())
    now = datetime.now(UTC)
    statement = insert(allowlist_entries).values(
        id=entry_id,
        entry_type=entry_type,
        value=value,
        note=note,
        added_by=added_by,
        created_at=now,
        updated_at=now,
    )
    if connection is None:
        async with get_connection() as conn:
            await conn.execute(statement)
            await conn.commit()
        return entry_id
    await connection.execute(statement)
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


async def find_waitlist_entry(entry_type: str, value: str) -> dict | None:
    """Fetch a waitlist entry by its type and normalized value.

    Args:
        entry_type: The entry type, ``"email"`` or ``"github_username"``.
        value: The normalized entry value.

    Returns:
        dict | None: The entry row, or None when not found.
    """
    async with get_connection() as connection:
        result = await connection.execute(
            select(waitlist_entries).where(
                (waitlist_entries.c.entry_type == entry_type) & (waitlist_entries.c.value == value)
            )
        )
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def find_waitlist_entry_by_id(entry_id: str) -> dict | None:
    """Fetch a waitlist entry by its id.

    Args:
        entry_id: The waitlist entry id.

    Returns:
        dict | None: The entry row, or None when not found.
    """
    async with get_connection() as connection:
        result = await connection.execute(select(waitlist_entries).where(waitlist_entries.c.id == entry_id))
        row = result.fetchone()
    return dict(row._mapping) if row else None


async def insert_waitlist_entry(entry_type: str, value: str, note: str | None) -> str:
    """Create a new waitlist entry and return its id.

    Args:
        entry_type: The entry type, ``"email"`` or ``"github_username"``.
        value: The normalized entry value.
        note: Optional operational note (e.g. the GitHub email).

    Returns:
        str: The id of the created entry.
    """
    entry_id = str(uuid4())
    now = datetime.now(UTC)
    async with get_connection() as connection:
        await connection.execute(
            insert(waitlist_entries).values(
                id=entry_id,
                entry_type=entry_type,
                value=value,
                status="pending",
                note=note,
                created_at=now,
                updated_at=now,
            )
        )
        await connection.commit()
    return entry_id


async def update_waitlist_entry(
    entry_id: str,
    changes: WaitlistEntryUpdate,
    connection: AsyncSession | None = None,
) -> bool:
    """Apply a status transition to a waitlist entry by id.

    ``updated_at`` is always bumped. Fields left as None on the update keep
    their current column value; ``clear_approval`` resets the approval
    metadata columns to NULL.

    Args:
        entry_id: The waitlist entry id.
        changes: The status transition and column changes to apply.
        connection: An optional shared connection to run within; when omitted
            a new connection is opened and the change is committed.

    Returns:
        bool: True when a row was updated, False when none matched.
    """
    values: dict = {"updated_at": datetime.now(UTC), "status": changes.status}
    if changes.approved_by is not None:
        values["approved_by"] = changes.approved_by
    if changes.approved_at is not None:
        values["approved_at"] = changes.approved_at
    if changes.notified_at is not None:
        values["notified_at"] = changes.notified_at
    if changes.joined_at is not None:
        values["joined_at"] = changes.joined_at
    if changes.clear_approval:
        values.update(approved_by=None, approved_at=None, notified_at=None, joined_at=None)

    statement = (
        update(waitlist_entries)
        .where(waitlist_entries.c.id == entry_id)
        .values(**values)
        .returning(waitlist_entries.c.id)
    )
    if connection is None:
        async with get_connection() as conn:
            result = await conn.execute(statement)
            row = result.fetchone()
            await conn.commit()
        return row is not None
    result = await connection.execute(statement)
    row = result.fetchone()
    return row is not None


async def delete_waitlist_entry(entry_id: str) -> bool:
    """Delete a waitlist entry by its id.

    Args:
        entry_id: The waitlist entry id.

    Returns:
        bool: True when a row was deleted, False when none matched.
    """
    async with get_connection() as connection:
        result = await connection.execute(
            delete(waitlist_entries).where(waitlist_entries.c.id == entry_id).returning(waitlist_entries.c.id)
        )
        row = result.fetchone()
        await connection.commit()
    return row is not None


async def list_waitlist_entries(status: str | None = None) -> list[dict]:
    """List waitlist entries, optionally filtered by status.

    Args:
        status: Optional status filter (``pending``, ``approved``, ``rejected``
            or ``joined``); None returns every entry.

    Returns:
        list[dict]: The waitlist entry rows ordered by created time.
    """
    async with get_connection() as connection:
        statement = select(waitlist_entries).order_by(waitlist_entries.c.created_at)
        if status is not None:
            statement = statement.where(waitlist_entries.c.status == status)
        result = await connection.execute(statement)
        rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


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
    Only rows scoped to ``"project"`` are returned; user-shared rows are
    resolved separately via :func:`get_user_environments_decrypted`.

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
            select(project_environments).where(
                (project_environments.c.project_id == project_id) & (project_environments.c.scope == "project")
            )
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

    Only rows scoped to ``"project"`` are returned.

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
            select(project_environments).where(
                (project_environments.c.project_id == project_id) & (project_environments.c.scope == "project")
            )
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


async def _fetch_stored_encrypted_value(owner_column: Column, owner_id: str, scope: str, keys: list[str]) -> str | None:
    """Return the stored ciphertext of an existing encrypted row among ``keys``.

    Keys are tried in order, so callers list the current key first and the
    previous (pre-rename) key second.

    Args:
        owner_column: The owner column (``project_id`` or ``user_id``).
        owner_id: The owner id to match.
        scope: ``"project"`` or ``"user"``.
        keys: Candidate environment variable names, in preference order.

    Returns:
        str | None: The stored encrypted value, or None when no candidate
            row is encrypted.
    """
    async with get_connection() as connection:
        result = await connection.execute(
            select(project_environments.c.key, project_environments.c.value, project_environments.c.type).where(
                (owner_column == owner_id)
                & (project_environments.c.key.in_(keys))
                & (project_environments.c.scope == scope)
            )
        )
        rows = {row.key: row for row in result.fetchall()}
    for key in keys:
        row = rows.get(key)
        if row is not None and row.type == "encrypted":
            return row.value
    return None


async def _resolve_encrypted_env_value(
    *,
    key: str,
    value: str,
    previous_key: str | None,
    owner_column: Column,
    owner_id: str,
    scope: str,
) -> str:
    """Return the ciphertext to store for an encrypted environment variable.

    A non-blank ``value`` is encrypted fresh; a blank one reuses the stored
    ciphertext of the row under ``key`` or ``previous_key``, so editing or
    renaming an encrypted variable without re-entering the secret preserves
    it. Falls back to encrypting the blank value when no encrypted row exists.

    Args:
        key: The environment variable name.
        value: The new plaintext value, possibly blank.
        previous_key: Optional prior key when renaming an existing entry.
        owner_column: The owner column (``project_id`` or ``user_id``).
        owner_id: The owner id to match.
        scope: ``"project"`` or ``"user"``.

    Returns:
        str: The ciphertext to store.
    """
    from demetra.services.persistence.encryption import encrypt_str

    if value.strip():
        return encrypt_str(plaintext=value)
    keys = [key]
    if previous_key and previous_key != key:
        keys.append(previous_key)
    stored = await _fetch_stored_encrypted_value(owner_column=owner_column, owner_id=owner_id, scope=scope, keys=keys)
    return stored if stored is not None else encrypt_str(plaintext=value)


async def _delete_previous_environment_key(
    connection: AsyncSession,
    *,
    owner_column: Column,
    owner_id: str,
    key: str,
    previous_key: str | None,
    scope: str,
) -> None:
    """Delete the old row after an environment variable rename.

    No-op when the rename carries no previous key or it matches the new key.

    Args:
        connection: An open transaction to run the delete within.
        owner_column: The owner column (``project_id`` or ``user_id``).
        owner_id: The owner id to match.
        key: The new environment variable name.
        previous_key: Optional prior key when renaming an existing entry.
        scope: ``"project"`` or ``"user"``.
    """
    if not previous_key or previous_key == key:
        return
    await connection.execute(
        delete(project_environments).where(
            (owner_column == owner_id)
            & (project_environments.c.key == previous_key)
            & (project_environments.c.scope == scope)
        )
    )


async def upsert_project_environment(
    project_id: str,
    user_id: str,
    key: str,
    value: str,
    env_type: str = "text",
    previous_key: str | None = None,
) -> dict:
    """Create or update a project environment variable.

    Encrypted values are encrypted before storage. When ``value`` is blank
    the stored ciphertext of the row under ``key`` or ``previous_key`` is
    reused, so editing or renaming an encrypted variable without re-entering
    the secret preserves it. The row is scoped to ``"project"``.

    Args:
        project_id: The project id.
        user_id: The owning user id for verification.
        key: The environment variable name.
        value: The environment variable value.
        env_type: ``"text"`` or ``"encrypted"``.
        previous_key: Optional prior key when renaming an existing entry.

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

    stored_value: str
    if env_type == "encrypted":
        stored_value = await _resolve_encrypted_env_value(
            key=key,
            value=value,
            previous_key=previous_key,
            owner_column=project_environments.c.project_id,
            owner_id=project_id,
            scope="project",
        )
    else:
        stored_value = value

    async with get_transaction() as connection:
        result = await connection.execute(
            text(
                """
                INSERT INTO project_environment (id, project_id, key, value, type, scope)
                VALUES (:id, :project_id, :key, :value, :type, 'project')
                ON CONFLICT (project_id, key) WHERE project_id IS NOT NULL DO UPDATE SET
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
        row = result.fetchone()
        await _delete_previous_environment_key(
            connection=connection,
            owner_column=project_environments.c.project_id,
            owner_id=project_id,
            key=key,
            previous_key=previous_key,
            scope="project",
        )

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
                (project_environments.c.project_id == project_id)
                & (project_environments.c.key == key)
                & (project_environments.c.scope == "project")
            )
        )
        await connection.commit()


async def get_user_environments_decrypted(user_id: str) -> dict[str, str]:
    """Return the decrypted user-shared environment variables of a user.

    Encrypted values are decrypted on read; failures yield an empty value.
    Only rows scoped to ``"user"`` are returned.

    Args:
        user_id: The user id.

    Returns:
        dict[str, str]: The user-shared environment as a key-value mapping.
    """
    from demetra.services.persistence.encryption import decrypt_str

    async with get_connection() as connection:
        result = await connection.execute(
            select(project_environments).where(
                (project_environments.c.user_id == user_id) & (project_environments.c.scope == "user")
            )
        )
        rows = result.fetchall()

    env: dict[str, str] = {}
    for row in rows:
        if row.type == "encrypted":
            try:
                env[row.key] = decrypt_str(row.value)
            except ValueError:
                logger.exception("Failed to decrypt user env var '%s' for user '%s'", row.key, user_id)
                env[row.key] = ""
        else:
            env[row.key] = row.value
    return env


async def list_user_environments(user_id: str) -> list[dict]:
    """List a user's shared environment entries, masking sensitive values.

    Values are masked when the row is encrypted or when the key matches the
    sensitive-key pattern (``*TOKEN*|*SECRET*|*KEY*|*PASSWORD*``).

    Args:
        user_id: The user id.

    Returns:
        list[dict]: One entry per environment variable; sensitive values are
            replaced with a mask.
    """
    from demetra.library.models import ENCRYPTED_VALUE_MASK, is_sensitive_key

    async with get_connection() as connection:
        result = await connection.execute(
            select(project_environments).where(
                (project_environments.c.user_id == user_id) & (project_environments.c.scope == "user")
            )
        )
        rows = result.fetchall()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "key": row.key,
            "value": (ENCRYPTED_VALUE_MASK if row.type == "encrypted" or is_sensitive_key(row.key) else row.value),
            "type": row.type,
        }
        for row in rows
    ]


async def upsert_user_environment(
    user_id: str,
    key: str,
    value: str,
    env_type: str = "text",
    previous_key: str | None = None,
) -> dict:
    """Create or update a user-shared environment variable.

    Encrypted values are encrypted before storage. When ``value`` is blank
    the stored ciphertext of the row under ``key`` or ``previous_key`` is
    reused, so editing or renaming an encrypted variable without re-entering
    the secret preserves it. The row is scoped to ``"user"`` with no project
    link.

    Args:
        user_id: The user id.
        key: The environment variable name.
        value: The environment variable value.
        env_type: ``"text"`` or ``"encrypted"``.
        previous_key: Optional prior key when renaming an existing entry.

    Returns:
        dict: The created or updated entry with the value masked when
            encrypted.

    Raises:
        LookupError: When the user does not exist.
        RuntimeError: When the database returns no row.
    """
    from uuid import uuid4

    from demetra.library.models import ENCRYPTED_VALUE_MASK, is_sensitive_key

    if not await get_user_by_id(user_id=user_id):
        raise LookupError("User not found")

    stored_value: str
    if env_type == "encrypted":
        stored_value = await _resolve_encrypted_env_value(
            key=key,
            value=value,
            previous_key=previous_key,
            owner_column=project_environments.c.user_id,
            owner_id=user_id,
            scope="user",
        )
    else:
        stored_value = value

    async with get_transaction() as connection:
        result = await connection.execute(
            text(
                """
                INSERT INTO project_environment (id, user_id, key, value, type, scope)
                VALUES (:id, :user_id, :key, :value, :type, 'user')
                ON CONFLICT (user_id, key) WHERE user_id IS NOT NULL DO UPDATE SET
                    value = EXCLUDED.value,
                    type = EXCLUDED.type
                RETURNING id, type
                """
            ),
            {
                "id": str(uuid4()),
                "user_id": user_id,
                "key": key,
                "value": stored_value,
                "type": env_type,
            },
        )
        row = result.fetchone()
        await _delete_previous_environment_key(
            connection=connection,
            owner_column=project_environments.c.user_id,
            owner_id=user_id,
            key=key,
            previous_key=previous_key,
            scope="user",
        )

    if row is None:
        raise RuntimeError("Failed to insert user environment")

    return {
        "id": row.id,
        "user_id": user_id,
        "key": key,
        "value": ENCRYPTED_VALUE_MASK if env_type == "encrypted" or is_sensitive_key(key) else value,
        "type": row.type,
    }


async def delete_user_environment(user_id: str, key: str) -> None:
    """Delete a user-shared environment variable.

    Args:
        user_id: The user id.
        key: The environment variable name to delete.

    Raises:
        LookupError: When the user does not exist.
    """
    if not await get_user_by_id(user_id=user_id):
        raise LookupError("User not found")

    async with get_connection() as connection:
        await connection.execute(
            delete(project_environments).where(
                (project_environments.c.user_id == user_id)
                & (project_environments.c.key == key)
                & (project_environments.c.scope == "user")
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

    if not SAFE_TASK_ID_PATTERN.fullmatch(task_id):
        return False

    async with get_connection() as connection:
        result = await connection.execute(
            delete(sessions)
            .where((sessions.c.task_id == task_id) & (sessions.c.user_id == user_id))
            .returning(sessions.c.task_id)
        )
        row = result.fetchone()
        if not row:
            await connection.commit()
            return False
        await connection.execute(delete(session_history).where(session_history.c.task_id == task_id))
        await connection.execute(delete(agent_sessions).where(agent_sessions.c.task_id == task_id))
        await connection.commit()

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
