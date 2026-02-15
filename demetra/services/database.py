import sqlite3
from datetime import UTC

from demetra.models import Session
from demetra.settings import DB_PATH


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                ticket_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (ticket_id, session_id)
            )
            """
        )
        conn.commit()


def create_session(ticket_id: str, session_id: str) -> Session:
    from datetime import datetime

    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (ticket_id, session_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (ticket_id, session_id, now, now),
        )
        conn.commit()
    return Session(ticket_id=ticket_id, session_id=session_id, created_at=now, updated_at=now)


def get_session(ticket_id: str) -> Session | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE ticket_id = ?",
            (ticket_id,),
        ).fetchone()
    if row:
        return Session(
            ticket_id=row["ticket_id"],
            session_id=row["session_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    return None
