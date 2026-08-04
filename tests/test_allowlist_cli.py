import asyncio
from uuid import uuid4

import pytest

from main import allowlist_cli

from demetra.services.allowlist import list_entries, remove_entry
from demetra.services.database import _engine_cache, create_user, delete_allowlist_entry, get_connection, text


_test_loop: asyncio.AbstractEventLoop | None = None


def _get_test_loop() -> asyncio.AbstractEventLoop:
    """Return the module-level event loop used for every CLI test call.

    A single loop keeps the cached async engines on a loop that stays open,
    so disposing their pools at teardown cannot hit an already-closed loop.
    """
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
def clean_allowlist():
    """Empty the allowlist table so list/seed counts are deterministic.

    The CLI tests share the local development database with the rest of the
    suite, so they must not assume the table starts empty.
    """

    async def _truncate() -> None:
        async with get_connection() as connection:
            await connection.execute(text("DELETE FROM allowlist_entries"))
            await connection.commit()

    _async_run(_truncate())
    yield
    _async_run(_dispose_engines())


def _run_cli(action, entry_type=None, value=None, note=None, dry_run=False) -> int:
    return _async_run(allowlist_cli(action=action, entry_type=entry_type, value=value, note=note, dry_run=dry_run))


def _unique_email() -> str:
    return f"cli-{uuid4().hex[:12]}@example.com"


async def _cleanup_user(user_id: str) -> None:
    async with get_connection() as connection:
        await connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        await connection.commit()


def test_add_happy_path(capsys):
    email = _unique_email()
    code = _run_cli(action="add", entry_type="email", value=email)
    assert code == 0
    assert "Allowlist entry added" in capsys.readouterr().out

    entries = _async_run(list_entries())
    assert any(e["entry_type"] == "email" and e["value"] == email for e in entries)
    _async_run(remove_entry(entry_type="email", value=email))


def test_add_duplicate_returns_error(capsys):
    email = _unique_email()
    code = _run_cli(action="add", entry_type="email", value=email)
    assert code == 0

    code = _run_cli(action="add", entry_type="email", value=email)
    assert code == 1
    assert "Entry already exists" in capsys.readouterr().out
    _async_run(remove_entry(entry_type="email", value=email))


def test_remove_present(capsys):
    email = _unique_email()
    _run_cli(action="add", entry_type="email", value=email)
    code = _run_cli(action="remove", entry_type="email", value=email)
    assert code == 0
    assert "Allowlist entry removed" in capsys.readouterr().out


def test_remove_absent_is_idempotent(capsys):
    code = _run_cli(action="remove", entry_type="email", value=_unique_email())
    assert code == 0
    assert "No allowlist entry" in capsys.readouterr().out


def test_list_empty(capsys):
    code = _run_cli(action="list")
    assert code == 0
    assert "No allowlist entries" in capsys.readouterr().out


def test_list_non_empty(capsys):
    email = _unique_email()
    _run_cli(action="add", entry_type="email", value=email)
    code = _run_cli(action="list")
    assert code == 0
    assert email in capsys.readouterr().out
    _async_run(remove_entry(entry_type="email", value=email))


def test_seed_existing_dry_run_reports_counts(capsys):
    email = _unique_email()
    user_id = _async_run(create_user(email=email))
    code = _run_cli(action="seed-existing", dry_run=True)
    assert code == 0
    out = capsys.readouterr().out
    assert "(dry-run)" in out
    assert "inserted" in out and "already present" in out and "skipped" in out

    entries = _async_run(list_entries())
    assert not any(e["value"] == email for e in entries)
    _async_run(_cleanup_user(user_id))
    _async_run(delete_allowlist_entry(entry_type="email", value=email))


def test_seed_existing_inserts_and_is_idempotent(capsys):
    email = _unique_email()
    user_id = _async_run(create_user(email=email))
    code = _run_cli(action="seed-existing")
    assert code == 0

    entries = _async_run(list_entries())
    assert any(e["entry_type"] == "email" and e["value"] == email for e in entries)

    code = _run_cli(action="seed-existing")
    assert code == 0
    out = capsys.readouterr().out
    assert "0 inserted" in out and "already present" in out and "skipped" in out

    _async_run(_cleanup_user(user_id))
    _async_run(delete_allowlist_entry(entry_type="email", value=email))
