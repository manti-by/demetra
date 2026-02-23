from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import aiosqlite
from aiosqlite import Connection

from demetra.models import Session
from demetra.settings import DB_PATH


@asynccontextmanager
async def get_connection() -> AsyncGenerator[Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = await aiosqlite.connect(DB_PATH)
    connection.row_factory = aiosqlite.Row
    try:
        yield connection
    finally:
        await connection.close()


async def init_db() -> None:
    async with get_connection() as connection:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                task_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (task_id, session_id)
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
        await connection.commit()


async def create_session(task_id: str, session_id: str) -> Session:
    now = datetime.now(UTC).isoformat()
    async with get_connection() as connection:
        await connection.execute(
            "INSERT INTO sessions (task_id, session_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (task_id, session_id, now, now),
        )
        await connection.commit()
    return Session(task_id=task_id, session_id=session_id, created_at=now, updated_at=now)


async def get_session(task_id: str) -> Session | None:
    async with get_connection() as connection:
        cursor = await connection.execute("SELECT * FROM sessions WHERE task_id = ?", (task_id,))
        row = await cursor.fetchone()
    if row:
        return Session(
            task_id=row["task_id"],
            session_id=row["session_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    return None


async def save_oauth_token(service: str, access_token: str, refresh_token: str | None, expires_in: int) -> None:
    expires_at = datetime.now(UTC).timestamp() + expires_in
    async with get_connection() as connection:
        await connection.execute(
            """
            INSERT OR REPLACE INTO oauth_tokens (service, access_token, refresh_token, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (service, access_token, refresh_token, expires_at),
        )
        await connection.commit()


async def get_oauth_token(service: str) -> tuple[str, str] | None:
    async with get_connection() as connection:
        cursor = await connection.execute(
            "SELECT access_token, expires_at FROM oauth_tokens WHERE service = ?", (service,)
        )
        row = await cursor.fetchone()
    if row:
        expires_at = float(row["expires_at"])
        if datetime.now(UTC).timestamp() < expires_at:
            return row["access_token"], str(expires_at)
    return None
