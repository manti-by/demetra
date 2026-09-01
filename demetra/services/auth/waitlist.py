import logging
from datetime import UTC, datetime
from typing import get_args

from rich.console import Console
from rich.table import Table
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from demetra.library.exceptions import AuthError
from demetra.library.types import WaitlistEntryType, WaitlistStatus
from demetra.services.auth.allowlist import add_entry, find_allowlist_entry, normalize_email, normalize_github_login
from demetra.services.persistence.database import (
    delete_waitlist_entry,
    find_waitlist_entry,
    find_waitlist_entry_by_id,
    init_db,
    insert_waitlist_entry,
    list_waitlist_entries,
    update_waitlist_entry,
)
from demetra.services.runtime.tui import print_message


logger = logging.getLogger(__name__)

VALID_ENTRY_TYPES = get_args(WaitlistEntryType)

VALID_STATUSES = get_args(WaitlistStatus)


def normalize_value(entry_type: str, value: str) -> str:
    """Normalize a waitlist value for the given entry type.

    Args:
        entry_type: The entry type, ``"email"`` or ``"github_username"``.
        value: The raw value to normalize.

    Returns:
        str: The normalized value.

    Raises:
        ValueError: When the entry type is not valid.
    """
    if entry_type == "email":
        return normalize_email(value)
    if entry_type == "github_username":
        return normalize_github_login(value)
    raise ValueError(f"Invalid entry type: {entry_type}")


def send_approval_email(entry: dict) -> bool:
    """Notify an approved waitlist entry by email.

    There is currently no SMTP/provider service in the codebase (see the
    waitlist ticket's open item), so this is a pluggable, log-only notifier:
    it writes the approval message to the log and console. Swapping in a real
    provider (SMTP/Resend/Postmark) only requires replacing the body of this
    function.

    The recipient is the ``value`` for ``email`` entries but the ``note``
    (the GitHub profile email) for ``github_username`` entries; when no
    address is available the call is a no-op so a real provider never tries
    to mail a GitHub login.

    Args:
        entry: The waitlist entry row that was just approved.

    Returns:
        bool: True when a notification was sent, False when skipped.
    """
    if entry["entry_type"] == "github_username":
        recipient = entry.get("note")
    else:
        recipient = entry["value"]
    if not recipient:
        return False
    print_message(
        f"[waitlist] approval email to {recipient}: You're approved! You can now sign in.",
        style="info",
    )
    return True


async def join_waitlist(entry_type: str, value: str, note: str | None = None) -> str:
    """Record a blocked user's interest in the waitlist, returning the entry id.

    Idempotent: when the normalized value is already present, the existing
    entry's id is returned and no new row is written (so repeated sign-up
    attempts after being added do not duplicate the audit record). A
    previously ``rejected`` entry is reopened to ``pending`` so the user can
    be reviewed again.

    Args:
        entry_type: The entry type, ``"email"`` or ``"github_username"``.
        value: The raw value to normalize and record.
        note: Optional operational note (e.g. the GitHub profile email).

    Returns:
        str: The id of the created (or existing) waitlist entry.

    Raises:
        ValueError: When the entry type is not valid.
    """
    if entry_type not in VALID_ENTRY_TYPES:
        raise ValueError(f"Invalid entry type: {entry_type}")

    normalized = normalize_value(entry_type, value)
    existing = await find_waitlist_entry(entry_type=entry_type, value=normalized)
    if existing:
        if existing["status"] == "rejected":
            await update_waitlist_entry(entry_id=existing["id"], status="pending")
            logger.info("Reopened waitlist entry %s (%s=%s)", existing["id"], entry_type, normalized)
        return existing["id"]

    try:
        return await insert_waitlist_entry(entry_type=entry_type, value=normalized, note=note)
    except IntegrityError:
        existing = await find_waitlist_entry(entry_type=entry_type, value=normalized)
        if existing:
            return existing["id"]
        raise AuthError("Failed to join waitlist") from None


async def find_pending_waitlist_entry(entry_type: str, value: str) -> dict | None:
    """Return a pending waitlist entry for the given type and value, if any.

    Args:
        entry_type: The entry type, ``"email"`` or ``"github_username"``.
        value: The raw value to normalize and match.

    Returns:
        dict | None: The pending entry row, or None when absent or not pending.
    """
    normalized = normalize_value(entry_type, value)
    entry = await find_waitlist_entry(entry_type=entry_type, value=normalized)
    if entry and entry["status"] == "pending":
        return entry
    return None


async def mark_waitlist_joined(entry_id: str) -> None:
    """Retain a waitlist entry for audit once the user signs up.

    The entry is not deleted; its status is flipped to ``joined`` so the
    audit trail survives. Idempotent: when the entry is already joined (or
    already has a ``joined_at``), nothing is rewritten, so repeated sign-ins
    never reset the original join timestamp.

    Args:
        entry_id: The waitlist entry id.
    """
    entry = await find_waitlist_entry_by_id(entry_id)
    if entry is None or entry.get("joined_at") is not None:
        return
    await update_waitlist_entry(entry_id=entry_id, status="joined", joined_at=datetime.now(UTC))


async def mark_waitlist_joined_by_value(entry_type: str, value: str) -> None:
    """Mark any existing waitlist entry as joined after a successful sign-in.

    Looks the entry up by its normalized type/value (no-op when absent), so
    the auth flows can record the audit transition without knowing the entry
    id up front.

    Args:
        entry_type: The entry type, ``"email"`` or ``"github_username"``.
        value: The raw value to normalize and match.
    """
    normalized = normalize_value(entry_type, value)
    entry = await find_waitlist_entry(entry_type=entry_type, value=normalized)
    if entry:
        await mark_waitlist_joined(entry_id=entry["id"])


async def approve_waitlist_entry(entry_id: str, approved_by: str | None = None) -> dict | None:
    """Promote a waitlist entry into the allowlist, unlocking sign-in.

    Looks up the waitlist row, inserts a matching ``allowlist_entries`` row
    via the existing allowlist service, sends the approval email, then flips
    the waitlist status to ``approved`` with ``notified_at`` only when the
    notification succeeded (a provider failure leaves the entry ``pending``
    so approval can be retried).

    Args:
        entry_id: The waitlist entry id.
        approved_by: Optional admin user id who approved the entry.

    Returns:
        dict | None: The resulting allowlist entry row.

    Raises:
        AuthError: When the waitlist entry does not exist or is not pending.
    """
    entry = await find_waitlist_entry_by_id(entry_id)
    if not entry:
        raise AuthError("Waitlist entry not found")
    if entry["status"] != "pending":
        raise AuthError(f"Waitlist entry cannot be approved (status: {entry['status']})")

    now = datetime.now(UTC)
    notified_at = now if send_approval_email(entry) else None

    try:
        await add_entry(
            entry_type=entry["entry_type"],
            value=entry["value"],
            note=entry.get("note"),
            added_by=approved_by,
        )
    except AuthError:
        # The allowlist row may already exist (e.g. an admin added it
        # directly); promotion still succeeds in that case.
        existing = await find_allowlist_entry(entry_type=entry["entry_type"], value=entry["value"])
        if existing is None:
            raise

    await update_waitlist_entry(
        entry_id=entry_id,
        status="approved",
        approved_by=approved_by,
        approved_at=now,
        notified_at=notified_at,
    )

    return await find_allowlist_entry(entry_type=entry["entry_type"], value=entry["value"])


async def remove_waitlist_entry(entry_id: str) -> bool:
    """Remove a waitlist entry by id.

    Args:
        entry_id: The waitlist entry id.

    Returns:
        bool: True when a row was deleted, False when none matched.
    """
    return await delete_waitlist_entry(entry_id)


async def list_entries(status: str | None = None) -> list[dict]:
    """List waitlist entries, optionally filtered by status.

    Args:
        status: Optional status filter; None returns every entry.

    Returns:
        list[dict]: The waitlist entry rows.

    Raises:
        ValueError: When the status filter is not a valid waitlist status.
    """
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    return await list_waitlist_entries(status=status)


async def waitlist_list(status: str | None = None) -> int:
    """Print the waitlist entries as a rich table.

    Args:
        status: Optional status filter.

    Returns:
        int: The process exit code, 0 on success.
    """
    entries = await list_entries(status=status)
    if not entries:
        print_message("No waitlist entries", style="info")
        return 0

    table = Table(title="Waitlist entries")
    for column in ("type", "value", "status", "note", "created_at", "approved_at"):
        table.add_column(column)
    for entry in entries:
        table.add_row(
            entry["entry_type"],
            entry["value"],
            entry["status"],
            entry["note"] or "",
            entry["created_at"].isoformat(),
            entry["approved_at"].isoformat() if entry.get("approved_at") else "",
        )
    Console(width=200).print(table)
    return 0


async def waitlist_approve(entry_id: str, approved_by: str | None = None) -> int:
    """Approve a waitlist entry from the CLI.

    Args:
        entry_id: The waitlist entry id.
        approved_by: Optional admin user id recorded on approve.

    Returns:
        int: The process exit code, 0 on success and 1 on failure.
    """
    try:
        await approve_waitlist_entry(entry_id=entry_id, approved_by=approved_by)
    except AuthError as e:
        print_message(str(e), style="error")
        return 1
    print_message("Waitlist entry approved and added to allowlist", style="success")
    return 0


async def waitlist_remove(entry_id: str) -> int:
    """Remove a waitlist entry from the CLI.

    Args:
        entry_id: The waitlist entry id.

    Returns:
        int: The process exit code, 0 on success.
    """
    if await remove_waitlist_entry(entry_id):
        print_message("Waitlist entry removed", style="success")
    else:
        print_message("No waitlist entry to remove", style="info")
    return 0


async def waitlist_cli(
    action: str, entry_id: str | None, status: str | None = None, approved_by: str | None = None
) -> int:
    """Run a waitlist management subcommand.

    Args:
        action: The sub-action: ``list``, ``approve`` or ``remove``.
        entry_id: The entry id for approve/remove.
        status: Optional status filter for list.
        approved_by: Optional admin user id recorded on approve.

    Returns:
        int: The process exit code.
    """
    try:
        await init_db()
    except SQLAlchemyError as e:
        print_message(f"Database error: {e}", style="error")
        return 1

    try:
        if action == "list":
            return await waitlist_list(status=status)
        if action == "approve":
            if not entry_id:
                print_message("Approving requires --waitlist-entry-id", style="error")
                return 1
            return await waitlist_approve(entry_id, approved_by=approved_by)
        if action == "remove":
            if not entry_id:
                print_message("Removing requires --waitlist-entry-id", style="error")
                return 1
            return await waitlist_remove(entry_id)
        print_message(f"Unknown waitlist action: {action}", style="error")
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
