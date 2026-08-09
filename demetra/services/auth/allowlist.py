import json
from pathlib import Path

from rich.console import Console
from rich.table import Table
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from demetra.library.exceptions import AuthError
from demetra.services.persistence.database import (
    delete_allowlist_entry,
    find_allowlist_entry,
    get_user_by_email,
    get_user_by_github_id,
    init_db,
    insert_allowlist_entry,
    list_allowlist_entries,
    list_user_allowlist_seed_rows,
)
from demetra.services.runtime.tui import print_message
from demetra.settings import ALLOWLIST_ENABLED, ALLOWLIST_SEED_FILE


VALID_ENTRY_TYPES = ("email", "github_username")


def is_allowlist_enabled() -> bool:
    """Return whether the allowlist gate is enabled.

    Returns:
        bool: The ``ALLOWLIST_ENABLED`` constant from ``demetra.settings``.
    """
    return ALLOWLIST_ENABLED


def normalize_email(value: str) -> str:
    """Normalize an email address for storage and matching.

    Args:
        value: The raw email address.

    Returns:
        str: The stripped, lowercased address.
    """
    return value.strip().lower()


def normalize_github_login(value: str) -> str:
    """Normalize a GitHub username for storage and matching.

    Args:
        value: The raw GitHub username.

    Returns:
        str: The stripped, lowercased username.
    """
    return value.strip().lower()


def normalize_value(entry_type: str, value: str) -> str:
    if entry_type == "email":
        return normalize_email(value)
    if entry_type == "github_username":
        return normalize_github_login(value)
    raise ValueError(f"Invalid entry type: {entry_type}")


async def is_email_allowed(email: str, user_data: dict | None = None) -> bool:
    """Return whether an email address may sign up or log in.

    Disabled allowlist always permits. An existing admin user (matched by the
    normalized email) always passes. Otherwise an ``email`` allowlist entry for
    the normalized address is required.

    Args:
        email: The raw email address.
        user_data: An already-fetched user row, when the caller has one, to
            avoid a redundant lookup.

    Returns:
        bool: True when the email is allowed.
    """
    if not is_allowlist_enabled():
        return True

    normalized = normalize_email(email)
    if user_data is None:
        user_data = await get_user_by_email(email=normalized)
    if user_data and user_data.get("role") == "admin":
        return True

    return await find_allowlist_entry(entry_type="email", value=normalized) is not None


async def is_github_login_allowed(login: str, email: str | None, github_id: str | None) -> bool:
    """Return whether a GitHub login may authenticate.

    Disabled allowlist always permits. An existing admin user (matched by the
    immutable GitHub account id) always passes. Otherwise a
    ``github_username`` entry for the login or an ``email`` entry for the
    non-null email is required (OR-match).

    Args:
        login: The GitHub login (username).
        email: The GitHub profile email, if any.
        github_id: The immutable GitHub account id.

    Returns:
        bool: True when the GitHub login is allowed.
    """
    if not is_allowlist_enabled():
        return True

    if github_id:
        user_data = await get_user_by_github_id(github_id=github_id)
        if user_data and user_data.get("role") == "admin":
            return True

    normalized_login = normalize_github_login(login)

    if await find_allowlist_entry(entry_type="github_username", value=normalized_login):
        return True

    if email:
        normalized_email = normalize_email(email)
        if await find_allowlist_entry(entry_type="email", value=normalized_email):
            return True

    return False


async def add_entry(entry_type: str, value: str, note: str | None, added_by: str | None) -> str:
    """Add an entry to the allowlist.

    Args:
        entry_type: The entry type, ``"email"`` or ``"github_username"``.
        value: The raw value to normalize and store.
        note: Optional operational note.
        added_by: Optional user id who added the entry.

    Returns:
        str: The id of the created entry.

    Raises:
        ValueError: When the entry type is not valid.
        AuthError: When the normalized entry already exists.
    """
    if entry_type not in VALID_ENTRY_TYPES:
        raise ValueError(f"Invalid entry type: {entry_type}")

    normalized = normalize_value(entry_type, value)
    existing = await find_allowlist_entry(entry_type=entry_type, value=normalized)
    if existing:
        raise AuthError("Entry already exists")

    try:
        return await insert_allowlist_entry(entry_type=entry_type, value=normalized, note=note, added_by=added_by)
    except IntegrityError as e:
        raise AuthError("Entry already exists") from e


async def remove_entry(entry_type: str, value: str) -> bool:
    """Remove an entry from the allowlist.

    Args:
        entry_type: The entry type, ``"email"`` or ``"github_username"``.
        value: The raw value to normalize and remove.

    Returns:
        bool: True when a row was deleted, False when none matched.
    """
    if entry_type not in VALID_ENTRY_TYPES:
        raise ValueError(f"Invalid entry type: {entry_type}")

    normalized = normalize_value(entry_type, value)
    return await delete_allowlist_entry(entry_type=entry_type, value=normalized)


async def list_entries() -> list[dict]:
    """List all allowlist entries.

    Returns:
        list[dict]: The allowlist entry rows.
    """
    return await list_allowlist_entries()


async def seed_allowlist_rows(dry_run: bool, rows: list[dict]) -> dict[str, int]:
    """Insert allowlist seed rows, reporting inserted/already-present/skipped counts.

    Each row must carry ``entry_type`` and ``value`` keys; ``note`` and
    ``source_user_id`` are optional. Rows with a missing or empty normalized
    value are counted as skipped. In dry-run mode the report is computed
    without writing.

    Args:
        dry_run: When True, report counts without inserting rows.
        rows: The seed rows to process.

    Returns:
        dict[str, int]: Counts of ``inserted``, ``already_present`` and
            ``skipped`` rows.
    """
    inserted = 0
    already_present = 0
    skipped = 0

    for row in rows:
        entry_type = row["entry_type"]
        value = row["value"]
        if value is None:
            skipped += 1
            continue

        normalized = normalize_value(entry_type, value)
        if not normalized:
            skipped += 1
            continue

        if await find_allowlist_entry(entry_type=entry_type, value=normalized):
            already_present += 1
            continue

        if dry_run:
            inserted += 1
            continue

        try:
            await insert_allowlist_entry(
                entry_type=entry_type,
                value=normalized,
                note=row.get("note"),
                added_by=row.get("source_user_id"),
            )
        except IntegrityError:
            already_present += 1
        else:
            inserted += 1

    return {"inserted": inserted, "already_present": already_present, "skipped": skipped}


async def seed_existing_users(dry_run: bool) -> dict[str, int]:
    """Backfill the allowlist from every current user.

    Each user yields an ``email`` and a ``github_username`` seed row. Rows with
    a missing value are counted as skipped. In dry-run mode the report is
    computed without writing.

    Args:
        dry_run: When True, report counts without inserting rows.

    Returns:
        dict[str, int]: Counts of ``inserted``, ``already_present`` and
            ``skipped`` rows.
    """
    rows = await list_user_allowlist_seed_rows()
    return await seed_allowlist_rows(dry_run=dry_run, rows=rows)


def load_seed_file(path: str) -> list[dict]:
    """Load allowlist seed entries from a JSON file.

    The file must contain a JSON array of objects. Each object requires a
    supported ``entry_type`` (``"email"`` or ``"github_username"``) and a
    non-empty string ``value``; ``note`` is optional and must be a string.

    Args:
        path: Filesystem path to the JSON seed file.

    Returns:
        list[dict]: The parsed seed entries.

    Raises:
        ValueError: When the file cannot be read or parsed, or any entry is
            malformed.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to load seed file {path}: {e}") from e
    if not isinstance(raw, list):
        raise ValueError(f"Seed file {path} must contain a JSON array")

    entries: list[dict] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"Seed file {path}: entry {index} must be an object")
        entry_type = entry.get("entry_type")
        if entry_type not in VALID_ENTRY_TYPES:
            raise ValueError(
                f"Seed file {path}: entry {index} has invalid entry_type {entry_type!r}; "
                f"expected one of {', '.join(VALID_ENTRY_TYPES)}"
            )
        value = entry.get("value")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Seed file {path}: entry {index} must have a non-empty string value")
        note = entry.get("note")
        if note is not None and not isinstance(note, str):
            raise ValueError(f"Seed file {path}: entry {index} note must be a string")
        entries.append(entry)

    return entries


async def allowlist_add(entry_type: str, value: str, note: str | None) -> int:
    await add_entry(entry_type=entry_type, value=value, note=note, added_by=None)
    print_message("Allowlist entry added", style="success")
    return 0


async def allowlist_remove(entry_type: str, value: str) -> int:
    if await remove_entry(entry_type=entry_type, value=value):
        print_message("Allowlist entry removed", style="success")
    else:
        print_message("No allowlist entry to remove", style="info")
    return 0


async def allowlist_list() -> int:
    entries = await list_entries()
    if not entries:
        print_message("No allowlist entries", style="info")
        return 0

    table = Table(title="Allowlist entries")
    for column in ("type", "value", "note", "added_by", "created_at"):
        table.add_column(column)
    for entry in entries:
        table.add_row(
            entry["entry_type"],
            entry["value"],
            entry["note"] or "",
            entry["added_by"] or "",
            entry["created_at"].isoformat(),
        )
    Console(width=200).print(table)
    return 0


async def allowlist_seed_existing(dry_run: bool) -> int:
    if ALLOWLIST_SEED_FILE:
        try:
            rows = load_seed_file(ALLOWLIST_SEED_FILE)
        except ValueError as e:
            print_message(str(e), style="error")
            return 1
        counts = await seed_allowlist_rows(dry_run=dry_run, rows=rows)
        prefix = "(dry-run) " if dry_run else ""
        print_message(
            f"{prefix}seeded {counts['inserted']} entries from {ALLOWLIST_SEED_FILE}: "
            f"{counts['already_present']} already present, {counts['skipped']} skipped",
            style="result",
        )
        return 0

    counts = await seed_existing_users(dry_run=dry_run)
    prefix = "(dry-run) " if dry_run else ""
    print_message(
        f"{prefix}seed-existing: {counts['inserted']} inserted, "
        f"{counts['already_present']} already present, {counts['skipped']} skipped",
        style="result",
    )
    return 0


async def allowlist_cli(action: str, entry_type: str | None, value: str | None, note: str | None, dry_run: bool) -> int:
    """Run an allowlist management subcommand.

    Args:
        action: The sub-action: ``add``, ``remove``, ``list`` or ``seed-existing``.
        entry_type: Entry type for add/remove.
        value: Entry value for add/remove.
        note: Optional note for add.
        dry_run: Whether seed-existing should avoid writing.

    Returns:
        int: The process exit code.
    """
    try:
        await init_db()
    except SQLAlchemyError as e:
        print_message(f"Database error: {e}", style="error")
        return 1

    try:
        if action == "add":
            return await allowlist_add(entry_type=entry_type or "", value=value or "", note=note)
        if action == "remove":
            return await allowlist_remove(entry_type=entry_type or "", value=value or "")
        if action == "list":
            return await allowlist_list()
        if action == "seed-existing":
            return await allowlist_seed_existing(dry_run=dry_run)
        print_message(f"Unknown allowlist action: {action}", style="error")
        return 1
    except AuthError as e:
        print_message(str(e), style="error")
        return 1
    except ValueError as e:
        print_message(str(e), style="error")
        return 1
    except SQLAlchemyError as e:
        print_message(f"Database error: {e}", style="error")
        return 1
