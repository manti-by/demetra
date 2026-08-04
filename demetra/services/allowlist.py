import json
import os
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from demetra.library.exceptions import AuthError
from demetra.services.database import (
    delete_allowlist_entry,
    find_allowlist_entry,
    get_user_by_email,
    get_user_by_github_username,
    insert_allowlist_entry,
    list_allowlist_entries,
    list_user_allowlist_seed_rows,
)


VALID_ENTRY_TYPES = ("email", "github_username")


def is_allowlist_enabled() -> bool:
    """Return whether the allowlist gate is enabled.

    Reads ``IS_ALLOWLIST_ENABLED`` from the environment on every call so test
    suites can flip it with ``monkeypatch.setenv`` without reloading settings.

    Returns:
        bool: True when the environment variable resolves to ``"true"``.
    """
    return os.environ.get("IS_ALLOWLIST_ENABLED", "false").lower() == "true"


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


def _normalize_value(entry_type: str, value: str) -> str:
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


async def is_github_login_allowed(login: str, email: str | None) -> bool:
    """Return whether a GitHub login may authenticate.

    Disabled allowlist always permits. An existing admin user (matched by the
    GitHub login) always passes. Otherwise a ``github_username`` entry for the
    login or an ``email`` entry for the non-null email is required (OR-match).

    Args:
        login: The GitHub login (username).
        email: The GitHub profile email, if any.

    Returns:
        bool: True when the GitHub login is allowed.
    """
    if not is_allowlist_enabled():
        return True

    normalized_login = normalize_github_login(login)
    user_data = await get_user_by_github_username(github_username=normalized_login)
    if user_data and user_data.get("role") == "admin":
        return True

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

    normalized = _normalize_value(entry_type, value)
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

    normalized = _normalize_value(entry_type, value)
    return await delete_allowlist_entry(entry_type=entry_type, value=normalized)


async def list_entries() -> list[dict]:
    """List all allowlist entries.

    Returns:
        list[dict]: The allowlist entry rows.
    """
    return await list_allowlist_entries()


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
    seed_rows = await list_user_allowlist_seed_rows()

    inserted = 0
    already_present = 0
    skipped = 0

    for row in seed_rows:
        entry_type = row["entry_type"]
        value = row["value"]
        if value is None:
            skipped += 1
            continue

        normalized = _normalize_value(entry_type, value)
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
                entry_type=entry_type, value=normalized, note=None, added_by=row["source_user_id"]
            )
        except IntegrityError:
            already_present += 1
        else:
            inserted += 1

    return {"inserted": inserted, "already_present": already_present, "skipped": skipped}


def load_seed_file(path: str) -> list[dict]:
    """Load allowlist seed entries from a JSON file.

    The file must contain a JSON array of objects with ``entry_type`` and
    ``value`` keys, and optionally ``note``.

    Args:
        path: Filesystem path to the JSON seed file.

    Returns:
        list[dict]: The parsed seed entries.

    Raises:
        ValueError: When the file cannot be read or parsed into a list.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to load seed file {path}: {e}") from e

    if not isinstance(data, list):
        raise ValueError(f"Seed file {path} must contain a JSON array")

    return data
