from unittest.mock import patch
from uuid import uuid4

import pytest

from demetra.library.exceptions import AuthError, WaitlistedError
from demetra.library.models import GitHubUser
from demetra.services.auth import (
    approve_waitlist_entry,
    authenticate_user,
    find_pending_waitlist_entry,
    join_waitlist,
    list_waitlist_entries,
    remove_waitlist_entry,
    signup_with_password,
)
from demetra.services.auth.allowlist import is_email_allowed
from demetra.services.persistence.database import update_waitlist_entry


def _unique_email() -> str:
    return f"waitlist-{uuid4().hex[:12]}@example.com"


def _unique_github() -> str:
    return f"gh-wl-{uuid4().hex[:8]}"


class TestJoinWaitlist:
    @pytest.mark.asyncio
    async def test_join_creates_pending_email_entry(self, allowlist_seeded):
        email = _unique_email()
        entry_id = await join_waitlist(entry_type="email", value=email)
        entry = await find_pending_waitlist_entry(entry_type="email", value=email)
        assert entry is not None
        assert entry["id"] == entry_id
        assert entry["status"] == "pending"

    @pytest.mark.asyncio
    async def test_join_is_idempotent(self, allowlist_seeded):
        email = _unique_email()
        first = await join_waitlist(entry_type="email", value=email)
        second = await join_waitlist(entry_type="email", value=email)
        assert first == second
        entries = await list_waitlist_entries()
        matching = [e for e in entries if e["value"] == email]
        assert len(matching) == 1

    @pytest.mark.asyncio
    async def test_join_normalizes_email(self, allowlist_seeded):
        email = _unique_email()
        await join_waitlist(entry_type="email", value=email.upper())
        assert await find_pending_waitlist_entry(entry_type="email", value=email) is not None

    @pytest.mark.asyncio
    async def test_join_github_username(self, allowlist_seeded):
        login = _unique_github()
        await join_waitlist(entry_type="github_username", value=login)
        assert await find_pending_waitlist_entry(entry_type="github_username", value=login) is not None

    @pytest.mark.asyncio
    async def test_join_invalid_type_raises(self, allowlist_seeded):
        with pytest.raises(ValueError, match="Invalid entry type"):
            await join_waitlist(entry_type="phone", value="123")

    @pytest.mark.asyncio
    async def test_join_reopens_rejected_entry(self, allowlist_seeded):
        email = _unique_email()
        entry_id = await join_waitlist(entry_type="email", value=email)
        await update_waitlist_entry(entry_id=entry_id, status="rejected")

        again = await join_waitlist(entry_type="email", value=email)
        assert again == entry_id
        entry = await find_pending_waitlist_entry(entry_type="email", value=email)
        assert entry is not None
        assert entry["status"] == "pending"


class TestApproveWaitlist:
    @pytest.mark.asyncio
    async def test_approve_adds_to_allowlist_and_user_can_signup(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        entry_id = await join_waitlist(entry_type="email", value=email)

        with patch("demetra.services.auth.waitlist.send_approval_email") as mock_send:
            await approve_waitlist_entry(entry_id=entry_id, approved_by="admin-1")

        mock_send.assert_called_once()

        # The allowlist gate now passes.
        assert await is_email_allowed(email=email) is True

        # The user can sign up with the same email.
        result = await signup_with_password(email=email, password="hunter2hunter2")
        assert result.user.email == email

    @pytest.mark.asyncio
    async def test_approve_flips_status_and_sets_timestamps(self, allowlist_seeded):
        email = _unique_email()
        entry_id = await join_waitlist(entry_type="email", value=email)
        with patch("demetra.services.auth.waitlist.send_approval_email"):
            await approve_waitlist_entry(entry_id=entry_id, approved_by="admin-1")

        entries = await list_waitlist_entries()
        entry = next(e for e in entries if e["id"] == entry_id)
        assert entry["status"] == "approved"
        assert entry["approved_by"] == "admin-1"
        assert entry["approved_at"] is not None
        assert entry["notified_at"] is not None

    @pytest.mark.asyncio
    async def test_approve_missing_entry_raises(self, allowlist_seeded):
        with pytest.raises(AuthError, match="Waitlist entry not found"):
            await approve_waitlist_entry(entry_id="missing", approved_by=None)

    @pytest.mark.asyncio
    async def test_approve_already_approved_raises(self, allowlist_seeded):
        email = _unique_email()
        entry_id = await join_waitlist(entry_type="email", value=email)
        with patch("demetra.services.auth.waitlist.send_approval_email"):
            await approve_waitlist_entry(entry_id=entry_id, approved_by=None)
        with pytest.raises(AuthError, match="cannot be approved"):
            await approve_waitlist_entry(entry_id=entry_id, approved_by=None)

    @pytest.mark.asyncio
    async def test_approve_joined_entry_raises_and_keeps_audit(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        entry_id = await join_waitlist(entry_type="email", value=email)
        with patch("demetra.services.auth.waitlist.send_approval_email"):
            await approve_waitlist_entry(entry_id=entry_id, approved_by=None)

        # The user signs up, flipping the entry to joined.
        await signup_with_password(email=email, password="hunter2hunter2")

        with pytest.raises(AuthError, match="cannot be approved"):
            await approve_waitlist_entry(entry_id=entry_id, approved_by="admin-1")

        # The audit trail is not corrupted: still joined, not stamped approved.
        entries = await list_waitlist_entries()
        entry = next(e for e in entries if e["id"] == entry_id)
        assert entry["status"] == "joined"
        assert entry["joined_at"] is not None

    @pytest.mark.asyncio
    async def test_approve_github_without_email_leaves_notified_at_unset(self, allowlist_seeded):
        login = _unique_github()
        entry_id = await join_waitlist(entry_type="github_username", value=login)
        with patch("demetra.services.auth.waitlist.send_approval_email", return_value=False):
            await approve_waitlist_entry(entry_id=entry_id, approved_by=None)

        entries = await list_waitlist_entries()
        entry = next(e for e in entries if e["id"] == entry_id)
        assert entry["status"] == "approved"
        assert entry["notified_at"] is None

    @pytest.mark.asyncio
    async def test_approve_email_failure_keeps_entry_pending(self, allowlist_seeded):
        email = _unique_email()
        entry_id = await join_waitlist(entry_type="email", value=email)

        with patch("demetra.services.auth.waitlist.send_approval_email", side_effect=RuntimeError("smtp down")):
            with pytest.raises(RuntimeError, match="smtp down"):
                await approve_waitlist_entry(entry_id=entry_id, approved_by=None)

        entries = await list_waitlist_entries()
        entry = next(e for e in entries if e["id"] == entry_id)
        assert entry["status"] == "pending"
        assert entry["notified_at"] is None
        assert await is_email_allowed(email=email) is False


class TestWaitlistRetainedAfterSignup:
    @pytest.mark.asyncio
    async def test_waitlist_entry_kept_after_authenticate(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        entry_id = await join_waitlist(entry_type="email", value=email)
        with patch("demetra.services.auth.waitlist.send_approval_email"):
            await approve_waitlist_entry(entry_id=entry_id, approved_by=None)

        await signup_with_password(email=email, password="hunter2hunter2")

        entries = await list_waitlist_entries()
        entry = next(e for e in entries if e["id"] == entry_id)
        assert entry is not None  # kept for audit, not deleted
        assert entry["status"] == "joined"
        assert entry["joined_at"] is not None

    @pytest.mark.asyncio
    async def test_repeated_github_logins_do_not_reset_joined_at(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        login = _unique_github()
        github_user = GitHubUser(id=str(uuid4().int), login=login, email=email)

        with pytest.raises(WaitlistedError) as exc_info:
            await authenticate_user(github_user)
        assert exc_info.value.entry_id is not None
        with patch("demetra.services.auth.waitlist.send_approval_email"):
            await approve_waitlist_entry(entry_id=exc_info.value.entry_id, approved_by=None)

        await authenticate_user(github_user)
        entries = await list_waitlist_entries()
        joined_at = next(e for e in entries if e["value"] == login)["joined_at"]

        # A second GitHub login must not rewrite the audit timestamp.
        await authenticate_user(github_user)
        entries = await list_waitlist_entries()
        entry = next(e for e in entries if e["value"] == login)
        assert entry["joined_at"] == joined_at


class TestGithubWaitlist:
    @pytest.mark.asyncio
    async def test_github_non_allowlisted_joins_waitlist(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        github_user = GitHubUser(id=str(uuid4().int), login=_unique_github(), email=email)

        with pytest.raises(WaitlistedError) as exc_info:
            await authenticate_user(github_user)
        assert exc_info.value.entry_id is not None

        entry = await find_pending_waitlist_entry(entry_type="github_username", value=github_user.login)
        assert entry is not None
        assert entry["note"] == email

    @pytest.mark.asyncio
    async def test_github_approved_can_authenticate(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        login = _unique_github()
        github_user = GitHubUser(id=str(uuid4().int), login=login, email=email)

        with pytest.raises(WaitlistedError) as exc_info:
            await authenticate_user(github_user)
        assert exc_info.value.entry_id is not None

        with patch("demetra.services.auth.waitlist.send_approval_email"):
            await approve_waitlist_entry(entry_id=exc_info.value.entry_id, approved_by=None)

        result = await authenticate_user(github_user)
        assert result.user.github_username == login


class TestSendApprovalEmail:
    def test_email_entry_uses_value_as_recipient(self):
        from demetra.services.auth.waitlist import send_approval_email

        entry = {"entry_type": "email", "value": "person@example.com", "note": None}
        with patch("demetra.services.auth.waitlist.print_message") as mock_print:
            assert send_approval_email(entry) is True
        message = mock_print.call_args.args[0]
        assert "person@example.com" in message

    def test_github_entry_uses_note_email_as_recipient(self):
        from demetra.services.auth.waitlist import send_approval_email

        entry = {"entry_type": "github_username", "value": "octocat", "note": "octo@example.com"}
        with patch("demetra.services.auth.waitlist.print_message") as mock_print:
            assert send_approval_email(entry) is True
        message = mock_print.call_args.args[0]
        assert "octo@example.com" in message
        assert "octocat" not in message

    def test_github_entry_without_email_is_noop(self):
        from demetra.services.auth.waitlist import send_approval_email

        entry = {"entry_type": "github_username", "value": "octocat", "note": None}
        with patch("demetra.services.auth.waitlist.print_message") as mock_print:
            assert send_approval_email(entry) is False
        mock_print.assert_not_called()


class TestRemoveWaitlist:
    @pytest.mark.asyncio
    async def test_remove_deletes_entry(self, allowlist_seeded):
        email = _unique_email()
        entry_id = await join_waitlist(entry_type="email", value=email)
        assert await remove_waitlist_entry(entry_id=entry_id) is True
        assert await find_pending_waitlist_entry(entry_type="email", value=email) is None

    @pytest.mark.asyncio
    async def test_remove_absent_returns_false(self, allowlist_seeded):
        assert await remove_waitlist_entry(entry_id="missing") is False
