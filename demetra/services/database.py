from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import psycopg
import psycopg.rows
from psycopg import AsyncConnection

from demetra.library.models import Session
from demetra.settings import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


@asynccontextmanager
async def get_connection() -> AsyncGenerator[AsyncConnection]:
    conn = await AsyncConnection.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        row_factory=psycopg.rows.dict_row,  # ty: ignore[invalid-argument-type]
    )
    try:
        yield conn
    finally:
        await conn.close()


async def init_db() -> None:
    async with get_connection() as connection:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                task_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                build_plan TEXT NOT NULL DEFAULT '',
                posted_to_linear BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                service TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                expires_at TEXT NOT NULL
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS task_status (
                task_id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await connection.commit()


async def create_session(task_id: str, session_id: str) -> Session:
    now = datetime.now(UTC).isoformat()
    async with get_connection() as connection:
        await connection.execute(
            """
            INSERT INTO sessions (task_id, session_id, build_plan, posted_to_linear, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (task_id, session_id, "", False, now, now),
        )
        await connection.commit()
    return Session(
        task_id=task_id,
        session_id=session_id,
        build_plan="",
        posted_to_linear=False,
        created_at=now,
        updated_at=now,
    )


async def get_session(task_id: str) -> Session | None:
    async with get_connection() as connection:
        cursor = await connection.execute("SELECT * FROM sessions WHERE task_id = %s", (task_id,))
        row: dict = await cursor.fetchone()  # ty: ignore[invalid-assignment]
    if row:
        return Session(
            task_id=row["task_id"],
            session_id=row["session_id"],
            build_plan=row["build_plan"],
            posted_to_linear=bool(row["posted_to_linear"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    return None


async def save_session(task_id: str, session_id: str, build_plan: str) -> Session:
    now = datetime.now(UTC).isoformat()
    async with get_connection() as connection:
        await connection.execute(
            """
            INSERT INTO sessions (task_id, session_id, build_plan, posted_to_linear, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (task_id) DO UPDATE SET
                session_id = EXCLUDED.session_id,
                build_plan = EXCLUDED.build_plan,
                posted_to_linear = sessions.posted_to_linear OR EXCLUDED.posted_to_linear,
                created_at = COALESCE(sessions.created_at, EXCLUDED.created_at),
                updated_at = EXCLUDED.updated_at
            """,
            (task_id, session_id, build_plan, False, now, now),
        )
        await connection.commit()
        cursor = await connection.execute("SELECT * FROM sessions WHERE task_id = %s", (task_id,))
        row: dict = await cursor.fetchone()  # ty: ignore[invalid-assignment]
    if row:
        return Session(
            task_id=row["task_id"],
            session_id=row["session_id"],
            build_plan=row["build_plan"],
            posted_to_linear=bool(row["posted_to_linear"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    return Session(
        task_id=task_id,
        session_id=session_id,
        build_plan=build_plan,
        posted_to_linear=False,
        created_at=now,
        updated_at=now,
    )


async def mark_session_posted(task_id: str) -> None:
    now = datetime.now(UTC).isoformat()
    async with get_connection() as connection:
        await connection.execute(
            "UPDATE sessions SET posted_to_linear = %s, updated_at = %s WHERE task_id = %s",
            (True, now, task_id),
        )
        await connection.commit()


async def save_oauth_token(service: str, access_token: str, refresh_token: str | None, expires_in: int) -> None:
    expires_at = datetime.now(UTC).timestamp() + expires_in
    async with get_connection() as connection:
        await connection.execute(
            """
            INSERT INTO oauth_tokens (service, access_token, refresh_token, expires_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (service) DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                expires_at = EXCLUDED.expires_at
            """,
            (service, access_token, refresh_token, str(expires_at)),
        )
        await connection.commit()


async def get_oauth_token(service: str) -> tuple[str, str] | None:
    async with get_connection() as connection:
        cursor = await connection.execute(
            "SELECT access_token, expires_at FROM oauth_tokens WHERE service = %s", (service,)
        )
        row: dict = await cursor.fetchone()  # ty: ignore[invalid-assignment]
    if row:
        expires_at = float(row["expires_at"])
        if datetime.now(UTC).timestamp() < expires_at:
            return row["access_token"], str(expires_at)
    return None


async def add_pending_task(task_id: str, project_name: str) -> None:
    now = datetime.now(UTC).isoformat()
    async with get_connection() as connection:
        cursor = await connection.execute("SELECT created_at FROM task_status WHERE task_id = %s", (task_id,))
        row: dict = await cursor.fetchone()  # ty: ignore[invalid-assignment]
        created_at = row["created_at"] if row else now

        await connection.execute(
            """
            INSERT INTO task_status (task_id, project_name, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (task_id) DO UPDATE SET
                project_name = EXCLUDED.project_name,
                status = %s,
                updated_at = EXCLUDED.updated_at
            """,
            (task_id, project_name, "pending", created_at, now, "pending"),
        )
        await connection.commit()


async def get_task_status(task_id: str) -> str | None:
    async with get_connection() as connection:
        cursor = await connection.execute("SELECT status FROM task_status WHERE task_id = %s", (task_id,))
        row: dict = await cursor.fetchone()  # ty: ignore[invalid-assignment]
    return row["status"] if row else None


async def mark_task_processed(task_id: str) -> None:
    now = datetime.now(UTC).isoformat()
    async with get_connection() as connection:
        await connection.execute(
            "UPDATE task_status SET status = %s, updated_at = %s WHERE task_id = %s",
            ("processed", now, task_id),
        )
        await connection.commit()


async def mark_task_failed(task_id: str) -> None:
    now = datetime.now(UTC).isoformat()
    async with get_connection() as connection:
        await connection.execute(
            "UPDATE task_status SET status = %s, updated_at = %s WHERE task_id = %s",
            ("failed", now, task_id),
        )
        await connection.commit()


async def get_pending_task_ids() -> set[str]:
    async with get_connection() as connection:
        cursor = await connection.execute("SELECT task_id FROM task_status WHERE status NOT IN ('processed', 'failed')")
        rows: dict = await cursor.fetchall()  # ty: ignore[invalid-assignment]
    return {row["task_id"] for row in rows}
