from uuid import uuid4

import pytest

from demetra.library.exceptions import AuthError
from demetra.library.models import GitHubUser
from demetra.services import database as _database_module
from demetra.services.allowlist import (
    add_entry,
    is_allowlist_enabled,
    is_email_allowed,
    normalize_email,
    normalize_github_login,
    remove_entry,
)
from demetra.services.auth import (
    authenticate_user,
    login_with_password,
    signup_with_password,
)


def _unique_email() -> str:
    return f"allowlist-{uuid4().hex[:12]}@example.com"


async def _create_password_user(email: str) -> None:
    await signup_with_password(email=email, password="hunter2hunter2")


@pytest.mark.asyncio
async def test_is_allowlist_enabled_defaults_false(monkeypatch):
    monkeypatch.delenv("IS_ALLOWLIST_ENABLED", raising=False)
    assert is_allowlist_enabled() is False


@pytest.mark.asyncio
async def test_is_allowlist_enabled_reads_env_per_call(monkeypatch):
    monkeypatch.setenv("IS_ALLOWLIST_ENABLED", "true")
    assert is_allowlist_enabled() is True
    monkeypatch.setenv("IS_ALLOWLIST_ENABLED", "false")
    assert is_allowlist_enabled() is False


@pytest.mark.asyncio
async def test_normalize_email_lowercases_and_strips():
    assert normalize_email("  Foo@Example.COM  ") == "foo@example.com"


@pytest.mark.asyncio
async def test_normalize_github_login_lowercases_and_strips():
    assert normalize_github_login("  MixedCase  ") == "mixedcase"


class TestSignupWithPassword:
    @pytest.mark.asyncio
    async def test_signup_allows_when_flag_off(self, mock_jwt_settings):
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


class TestLoginWithPassword:
    @pytest.mark.asyncio
    async def test_login_allows_when_flag_off(self, mock_jwt_settings):
        email = _unique_email()
        await _create_password_user(email)
        result = await login_with_password(email=email, password="hunter2hunter2")
        assert result.user.email == email

    @pytest.mark.asyncio
    async def test_login_rejects_non_allowlisted_existing_user(self, mock_jwt_settings, monkeypatch):
        email = _unique_email()
        await _create_password_user(email)
        monkeypatch.setenv("IS_ALLOWLIST_ENABLED", "true")
        with pytest.raises(AuthError, match="Invalid email or password"):
            await login_with_password(email=email, password="hunter2hunter2")

    @pytest.mark.asyncio
    async def test_login_allows_allowlisted_existing_user(self, mock_jwt_settings, monkeypatch):
        email = _unique_email()
        await _create_password_user(email)
        await add_entry(entry_type="email", value=email, note=None, added_by=None)
        monkeypatch.setenv("IS_ALLOWLIST_ENABLED", "true")
        result = await login_with_password(email=email, password="hunter2hunter2")
        assert result.user.email == email

    @pytest.mark.asyncio
    async def test_login_rejects_unknown_email_with_generic_message(self, mock_jwt_settings, allowlist_seeded):
        with pytest.raises(AuthError, match="Invalid email or password"):
            await login_with_password(email=_unique_email(), password="hunter2hunter2")


class TestGitHubAuthenticate:
    @pytest.mark.asyncio
    async def test_github_allows_when_flag_off(self, mock_jwt_settings):
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
