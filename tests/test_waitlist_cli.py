import asyncio
from unittest.mock import patch
from uuid import uuid4

import pytest

from demetra.services.auth.waitlist import join_waitlist, waitlist_cli
from demetra.services.persistence.database import (
    _engine_cache,
    get_connection,
    list_waitlist_entries,
    text,
)


_test_loop: asyncio.AbstractEventLoop | None = None


def _get_test_loop() -> asyncio.AbstractEventLoop:
    """Return the module-level event loop used for every CLI test call."""
    global _test_loop
    if _test_loop is None or _test_loop.is_closed():
        _test_loop = asyncio.new_event_loop()
    return _test_loop


async def _dispose_engines() -> None:
    """Dispose the cached engines so their pools are released."""
    for engine in _engine_cache.values():
        await engine.dispose()
    _engine_cache.clear()


def _async_run(coro):
    """Run a coroutine on the shared loop and release the cached engines."""
    loop = _get_test_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(_dispose_engines())


@pytest.fixture(autouse=True)
def clean_waitlist():
    """Empty the waitlist table so list counts are deterministic."""

    async def _truncate() -> None:
        async with get_connection() as connection:
            await connection.execute(text("DELETE FROM waitlist_entries"))
            await connection.commit()

    _async_run(_truncate())
    yield
    _async_run(_dispose_engines())


def _unique_email() -> str:
    return f"cli-wl-{uuid4().hex[:12]}@example.com"


def _run_cli(action, entry_id=None, status=None, approved_by=None) -> int:
    return _async_run(waitlist_cli(action=action, entry_id=entry_id, status=status, approved_by=approved_by))


def test_list_empty(capsys):
    code = _run_cli(action="list")
    assert code == 0
    assert "No waitlist entries" in capsys.readouterr().out


def test_list_non_empty(capsys):
    email = _unique_email()
    _async_run(join_waitlist(entry_type="email", value=email))
    code = _run_cli(action="list")
    assert code == 0
    assert email in capsys.readouterr().out


def test_list_filters_by_status(capsys):
    email = _unique_email()
    _async_run(join_waitlist(entry_type="email", value=email))
    code = _run_cli(action="list", status="pending")
    assert code == 0
    assert email in capsys.readouterr().out

    code = _run_cli(action="list", status="approved")
    assert code == 0
    assert "No waitlist entries" in capsys.readouterr().out


def test_approve_adds_to_allowlist(capsys):
    email = _unique_email()
    entry_id = _async_run(join_waitlist(entry_type="email", value=email))
    with patch("demetra.services.auth.waitlist.send_approval_email"):
        code = _run_cli(action="approve", entry_id=entry_id)
    assert code == 0
    assert "approved" in capsys.readouterr().out

    entries = _async_run(list_waitlist_entries())
    entry = next(e for e in entries if e["id"] == entry_id)
    assert entry["status"] == "approved"


def test_approve_records_approved_by(capsys):
    email = _unique_email()
    entry_id = _async_run(join_waitlist(entry_type="email", value=email))
    with patch("demetra.services.auth.waitlist.send_approval_email"):
        code = _run_cli(action="approve", entry_id=entry_id, approved_by="admin-7")
    assert code == 0

    entries = _async_run(list_waitlist_entries())
    entry = next(e for e in entries if e["id"] == entry_id)
    assert entry["approved_by"] == "admin-7"


def test_approve_missing_entry_returns_error(capsys):
    code = _run_cli(action="approve", entry_id="missing")
    assert code == 1
    assert "Waitlist entry not found" in capsys.readouterr().out


def test_approve_without_entry_id_returns_error(capsys):
    code = _run_cli(action="approve")
    assert code == 1
    assert "--waitlist-entry-id" in capsys.readouterr().out


def test_remove_present(capsys):
    email = _unique_email()
    entry_id = _async_run(join_waitlist(entry_type="email", value=email))
    code = _run_cli(action="remove", entry_id=entry_id)
    assert code == 0
    assert "Waitlist entry removed" in capsys.readouterr().out


def test_remove_absent_is_idempotent(capsys):
    code = _run_cli(action="remove", entry_id="missing")
    assert code == 0
    assert "No waitlist entry" in capsys.readouterr().out
