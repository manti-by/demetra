from uuid import uuid4

import pytest

from demetra.library.exceptions import AuthError
from demetra.library.models import GitHubUser
from demetra.services.auth import (
    authenticate_user,
    login_with_password,
    signup_with_password,
)
from demetra.services.auth.allowlist import (
    add_entry,
    is_email_allowed,
    normalize_email,
    normalize_github_login,
    remove_entry,
)
from demetra.services.persistence import database as _database_module


def _unique_email() -> str:
    return f"allowlist-{uuid4().hex[:12]}@example.com"


async def _create_password_user(email: str) -> None:
    await signup_with_password(email=email, password="hunter2hunter2")


@pytest.mark.asyncio
async def test_normalize_email_lowercases_and_strips():
    assert normalize_email("  Foo@Example.COM  ") == "foo@example.com"


@pytest.mark.asyncio
async def test_normalize_github_login_lowercases_and_strips():
    assert normalize_github_login("  MixedCase  ") == "mixedcase"


class TestSignupWithPassword:
    @pytest.mark.asyncio
    async def test_signup_allows_when_flag_off(self, mock_jwt_settings, allowlist_disabled):
        email = _unique_email()
        result = await signup_with_password(email=email, password="hunter2hunter2")
        assert result.user.email == email

    @pytest.mark.asyncio
    async def test_signup_rejects_non_allowlisted_email(self, mock_jwt_settings, allowlist_seeded):
        with pytest.raises(AuthError, match="Email not authorized for registration"):
            await signup_with_password(email=_unique_email(), password="hunter2hunter2")

    @pytest.mark.asyncio
    async def test_signup_allows_allowlisted_email(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        await add_entry(entry_type="email", value=email, note=None, added_by=None)
        result = await signup_with_password(email=email, password="hunter2hunter2")
        assert result.user.email == email

    @pytest.mark.asyncio
    async def test_signup_allows_case_different_allowlisted_email(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        await add_entry(entry_type="email", value=email, note=None, added_by=None)
        result = await signup_with_password(email=email.upper(), password="hunter2hunter2")
        assert result.user.email == email

    @pytest.mark.asyncio
    async def test_signup_rejects_when_allowlist_on_but_empty_and_email_differs_from_admin(
        self, mock_jwt_settings, allowlist_seeded
    ):
        admin_email = _unique_email()
        await add_entry(entry_type="email", value=admin_email, note=None, added_by=None)
        user_id = (await signup_with_password(email=admin_email, password="hunter2hunter2")).user.id
        async with _database_module.get_connection() as connection:
            from sqlalchemy import text

            await connection.execute(text("UPDATE users SET role = 'admin' WHERE id = :id"), {"id": user_id})
            await connection.commit()

        await remove_entry(entry_type="email", value=admin_email)

        with pytest.raises(AuthError, match="Email not authorized for registration"):
            await signup_with_password(email=_unique_email(), password="hunter2hunter2")


class TestIsEmailAllowedUserData:
    @pytest.mark.asyncio
    async def test_rejects_user_data_with_user_role(self, allowlist_seeded):
        email = _unique_email()
        assert await is_email_allowed(email=email, user_data={"role": "user"}) is False

    @pytest.mark.asyncio
    async def test_passes_user_data_with_admin_role(self, allowlist_seeded):
        email = _unique_email()
        assert await is_email_allowed(email=email, user_data={"role": "admin"}) is True

    @pytest.mark.asyncio
    async def test_rejects_no_user_data_when_allowlist_empty(self, allowlist_seeded):
        email = _unique_email()
        assert await is_email_allowed(email=email) is False


class TestLoginWithPassword:
    @pytest.mark.asyncio
    async def test_login_allows_when_flag_off(self, mock_jwt_settings, allowlist_disabled):
        email = _unique_email()
        await _create_password_user(email)
        result = await login_with_password(email=email, password="hunter2hunter2")
        assert result.user.email == email

    @pytest.mark.asyncio
    async def test_login_rejects_non_allowlisted_existing_user(
        self, mock_jwt_settings, allowlist_disabled, monkeypatch
    ):
        email = _unique_email()
        await _create_password_user(email)
        monkeypatch.setattr("demetra.services.auth.allowlist.IS_ALLOWLIST_ENABLED", True)
        with pytest.raises(AuthError, match="Invalid email or password"):
            await login_with_password(email=email, password="hunter2hunter2")

    @pytest.mark.asyncio
    async def test_login_allows_allowlisted_existing_user(self, mock_jwt_settings, allowlist_disabled, monkeypatch):
        email = _unique_email()
        await _create_password_user(email)
        await add_entry(entry_type="email", value=email, note=None, added_by=None)
        monkeypatch.setattr("demetra.services.auth.allowlist.IS_ALLOWLIST_ENABLED", True)
        result = await login_with_password(email=email, password="hunter2hunter2")
        assert result.user.email == email

    @pytest.mark.asyncio
    async def test_login_rejects_unknown_email_with_generic_message(self, mock_jwt_settings, allowlist_seeded):
        with pytest.raises(AuthError, match="Invalid email or password"):
            await login_with_password(email=_unique_email(), password="hunter2hunter2")

    @pytest.mark.asyncio
    async def test_login_rejects_when_user_dropped_from_allowlist(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        await add_entry(entry_type="email", value=email, note=None, added_by=None)
        await _create_password_user(email)
        await remove_entry(entry_type="email", value=email)

        with pytest.raises(AuthError, match="Invalid email or password"):
            await login_with_password(email=email, password="hunter2hunter2")

    @pytest.mark.asyncio
    async def test_login_verifies_password_before_allowlist_check(
        self, mock_jwt_settings, allowlist_seeded, monkeypatch
    ):
        email = _unique_email()
        await add_entry(entry_type="email", value=email, note=None, added_by=None)
        await _create_password_user(email)

        calls: list[str] = []

        def fake_verify_password(plain: str, hashed: str) -> bool:
            calls.append("verify_password")
            return plain == "hunter2hunter2"

        async def fake_is_email_allowed(email: str, user_data: dict | None = None) -> bool:
            calls.append("is_email_allowed")
            return True

        monkeypatch.setattr("demetra.services.auth.verify_password", fake_verify_password)
        monkeypatch.setattr("demetra.services.auth.is_email_allowed", fake_is_email_allowed)

        result = await login_with_password(email=email, password="hunter2hunter2")
        assert result.user.email == email
        assert calls == ["verify_password", "is_email_allowed"]

    @pytest.mark.asyncio
    async def test_login_wrong_password_skips_allowlist_check(self, mock_jwt_settings, allowlist_seeded, monkeypatch):
        email = _unique_email()
        await add_entry(entry_type="email", value=email, note=None, added_by=None)
        await _create_password_user(email)

        is_email_allowed_called = False

        async def fake_is_email_allowed(email: str, user_data: dict | None = None) -> bool:
            nonlocal is_email_allowed_called
            is_email_allowed_called = True
            return True

        monkeypatch.setattr("demetra.services.auth.verify_password", lambda plain, hashed: False)
        monkeypatch.setattr("demetra.services.auth.is_email_allowed", fake_is_email_allowed)

        with pytest.raises(AuthError, match="Invalid email or password"):
            await login_with_password(email=email, password="wrongPassword1")
        assert is_email_allowed_called is False


class TestGitHubAuthenticate:
    @pytest.mark.asyncio
    async def test_github_allows_when_flag_off(self, mock_jwt_settings, allowlist_disabled):
        github_user = GitHubUser(id=str(uuid4().int), login=f"gh-{uuid4().hex[:8]}", email=_unique_email())
        result = await authenticate_user(github_user)
        assert result.user.github_username == github_user.login

    @pytest.mark.asyncio
    async def test_github_rejects_non_allowlisted_login(self, mock_jwt_settings, allowlist_seeded):
        github_user = GitHubUser(id=str(uuid4().int), login=f"gh-{uuid4().hex[:8]}", email=_unique_email())
        with pytest.raises(AuthError, match="GitHub account not authorized"):
            await authenticate_user(github_user)

    @pytest.mark.asyncio
    async def test_github_allows_allowlisted_login(self, mock_jwt_settings, allowlist_seeded):
        login = f"gh-{uuid4().hex[:8]}"
        github_user = GitHubUser(id=str(uuid4().int), login=login, email=_unique_email())
        await add_entry(entry_type="github_username", value=login, note=None, added_by=None)
        result = await authenticate_user(github_user)
        assert result.user.github_username == login

    @pytest.mark.asyncio
    async def test_github_allows_allowlisted_email(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        github_user = GitHubUser(id=str(uuid4().int), login=f"gh-{uuid4().hex[:8]}", email=email)
        await add_entry(entry_type="email", value=email, note=None, added_by=None)
        result = await authenticate_user(github_user)
        assert result.user.email == email

    @pytest.mark.asyncio
    async def test_github_login_or_match_with_existing_user(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        await add_entry(entry_type="email", value=email, note=None, added_by=None)
        github_user = GitHubUser(id=str(uuid4().int), login=f"gh-{uuid4().hex[:8]}", email=email)
        result = await authenticate_user(github_user)
        assert result.user.email == email

    @pytest.mark.asyncio
    async def test_github_rejects_when_email_is_null(self, mock_jwt_settings, allowlist_seeded):
        github_user = GitHubUser(id=str(uuid4().int), login=f"gh-{uuid4().hex[:8]}", email=None)
        with pytest.raises(AuthError, match="GitHub account not authorized"):
            await authenticate_user(github_user)


class TestAdminBypass:
    @pytest.mark.asyncio
    async def test_admin_email_gate_passes_without_entry(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        await add_entry(entry_type="email", value=email, note=None, added_by=None)
        user_id = (await signup_with_password(email=email, password="hunter2hunter2")).user.id
        async with _database_module.get_connection() as connection:
            from sqlalchemy import text

            await connection.execute(text("UPDATE users SET role = 'admin' WHERE id = :id"), {"id": user_id})
            await connection.commit()

        await remove_entry(entry_type="email", value=email)
        assert await is_email_allowed(email=email) is True

    @pytest.mark.asyncio
    async def test_admin_login_passes_without_entry(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        await add_entry(entry_type="email", value=email, note=None, added_by=None)
        user_id = (await signup_with_password(email=email, password="hunter2hunter2")).user.id
        async with _database_module.get_connection() as connection:
            from sqlalchemy import text

            await connection.execute(text("UPDATE users SET role = 'admin' WHERE id = :id"), {"id": user_id})
            await connection.commit()

        await remove_entry(entry_type="email", value=email)
        result = await login_with_password(email=email, password="hunter2hunter2")
        assert result.user.email == email

    @pytest.mark.asyncio
    async def test_admin_github_gate_passes_without_entry(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        login = f"gh-{uuid4().hex[:8]}"
        github_id = str(uuid4().int)
        await add_entry(entry_type="github_username", value=login, note=None, added_by=None)
        user_id = (await authenticate_user(GitHubUser(id=github_id, login=login, email=email))).user.id
        async with _database_module.get_connection() as connection:
            from sqlalchemy import text

            await connection.execute(text("UPDATE users SET role = 'admin' WHERE id = :id"), {"id": user_id})
            await connection.commit()

        await remove_entry(entry_type="github_username", value=login)
        github_user = GitHubUser(id=github_id, login=login, email=email)
        result = await authenticate_user(github_user)
        assert result.user.github_username == login

    @pytest.mark.asyncio
    async def test_admin_github_gate_rejects_reassigned_username(self, mock_jwt_settings, allowlist_seeded):
        email = _unique_email()
        login = f"gh-{uuid4().hex[:8]}"
        admin_github_id = str(uuid4().int)
        await add_entry(entry_type="github_username", value=login, note=None, added_by=None)
        user_id = (await authenticate_user(GitHubUser(id=admin_github_id, login=login, email=email))).user.id
        async with _database_module.get_connection() as connection:
            from sqlalchemy import text

            await connection.execute(text("UPDATE users SET role = 'admin' WHERE id = :id"), {"id": user_id})
            await connection.commit()

        await remove_entry(entry_type="github_username", value=login)
        intruder = GitHubUser(id=str(uuid4().int), login=login, email=_unique_email())
        with pytest.raises(AuthError, match="GitHub account not authorized"):
            await authenticate_user(intruder)


class TestEntryCrud:
    @pytest.mark.asyncio
    async def test_add_and_find_normalizes_email(self, allowlist_seeded):
        email = f"MixedCase-{uuid4().hex[:8]}@Example.com"
        await add_entry(entry_type="email", value=email, note="note", added_by=None)
        normalized = normalize_email(email)
        assert await is_email_allowed(email=normalized) is True
        await remove_entry(entry_type="email", value=normalized)

    @pytest.mark.asyncio
    async def test_add_duplicate_raises(self, allowlist_seeded):
        email = f"dup-{uuid4().hex[:8]}@example.com"
        await add_entry(entry_type="email", value=email, note=None, added_by=None)
        with pytest.raises(AuthError, match="Entry already exists"):
            await add_entry(entry_type="email", value=email, note=None, added_by=None)
        await remove_entry(entry_type="email", value=email)

    @pytest.mark.asyncio
    async def test_remove_absent_returns_false(self):
        assert await remove_entry(entry_type="email", value=f"missing-{uuid4().hex[:8]}@example.com") is False
