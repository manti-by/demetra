from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from fastapi.testclient import TestClient

from demetra.app import app
from demetra.library.exceptions import AuthError
from demetra.library.models import GitHubUser, UserResponse
from demetra.services.auth import (
    authenticate_user,
    create_jwt_token,
    exchange_code_for_token,
    get_current_user,
    get_github_auth_url,
    get_github_user,
    has_permission,
    login_with_password,
    signup_with_password,
    verify_jwt_token,
)


class TestAuthService:
    @pytest.fixture
    def mock_github_oauth_no_credentials(self, github_oauth_settings):
        github_oauth_settings["client_id"] = None
        github_oauth_settings["client_secret"] = None
        github_settings = {
            "path": "/usr/bin/gh",
            "oauth": github_oauth_settings,
            "webhook": {"secret": None},
        }
        with patch("demetra.services.auth.GITHUB", github_settings):
            yield

    @pytest.fixture
    def mock_jwt_no_key(self, jwt_settings):
        jwt_settings["secret_key"] = None
        with patch("demetra.services.auth.JWT", jwt_settings):
            yield

    @pytest.mark.asyncio
    async def test_get_github_auth_url_returns_url_and_state(self, mock_github_oauth_settings):
        url, state = get_github_auth_url()

        assert "github.com/login/oauth/authorize" in url
        assert "client_id=test_client_id" in url
        assert "state=" in url
        assert len(state) == 43

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_raises_without_credentials(self, mock_github_oauth_no_credentials):
        with pytest.raises(AuthError, match="GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET must be set"):
            await exchange_code_for_token("test_code")

    @pytest.mark.asyncio
    async def test_create_jwt_token_raises_without_secret_key(self, mock_jwt_no_key):
        with pytest.raises(AuthError, match="JWT_SECRET_KEY must be set"):
            create_jwt_token("user_id")

    @pytest.mark.asyncio
    async def test_create_jwt_token_returns_token_and_expiry(self, mock_jwt_settings):
        token, expires_at = create_jwt_token("user_id")

        assert token is not None
        assert expires_at is not None


class TestExchangeCodeForToken:
    @pytest.fixture(autouse=True)
    def setup(self, github_oauth_settings):
        self.github = {"path": "/usr/bin/gh", "oauth": github_oauth_settings, "webhook": {"secret": None}}

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_success(self):
        with (
            patch("demetra.services.auth.GITHUB", self.github),
            patch("aiohttp.ClientSession.post") as mock_post,
        ):
            mock_response = AsyncMock()
            mock_response.__aenter__.return_value = mock_response
            mock_response.raise_for_status = MagicMock()
            mock_response.json = AsyncMock(return_value={"access_token": "gho_test123"})
            mock_post.return_value = mock_response

            token = await exchange_code_for_token("test_code")
            assert token == "gho_test123"

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_missing_access_token(self):
        with (
            patch("demetra.services.auth.GITHUB", self.github),
            patch("aiohttp.ClientSession.post") as mock_post,
        ):
            mock_response = AsyncMock()
            mock_response.__aenter__.return_value = mock_response
            mock_response.raise_for_status = MagicMock()
            mock_response.json = AsyncMock(return_value={})
            mock_post.return_value = mock_response

            with pytest.raises(AuthError, match="No access token"):
                await exchange_code_for_token("test_code")

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_http_error(self):
        with (
            patch("demetra.services.auth.GITHUB", self.github),
            patch("aiohttp.ClientSession.post") as mock_post,
        ):
            mock_post.side_effect = aiohttp.ClientError("HTTP error")

            with pytest.raises(AuthError, match="OAuth token exchange error"):
                await exchange_code_for_token("test_code")


class TestGetGitHubUser:
    @pytest.fixture(autouse=True)
    def setup(self, github_oauth_settings):
        self.github = {"path": "/usr/bin/gh", "oauth": github_oauth_settings, "webhook": {"secret": None}}

    @pytest.mark.asyncio
    async def test_get_github_user_success(self):
        with (
            patch("demetra.services.auth.GITHUB", self.github),
            patch("aiohttp.ClientSession.get") as mock_get,
        ):
            mock_response = AsyncMock()
            mock_response.__aenter__.return_value = mock_response
            mock_response.raise_for_status = MagicMock()
            mock_response.json = AsyncMock(
                return_value={
                    "id": 12345,
                    "login": "testuser",
                    "email": "test@example.com",
                    "avatar_url": "https://avatars.com/u/12345",
                }
            )
            mock_get.return_value = mock_response

            user = await get_github_user("gho_test123")
            assert user.id == "12345"
            assert user.login == "testuser"
            assert user.email == "test@example.com"
            assert user.avatar_url == "https://avatars.com/u/12345"

    @pytest.mark.asyncio
    async def test_get_github_user_http_error(self):
        with (
            patch("demetra.services.auth.GITHUB", self.github),
            patch("aiohttp.ClientSession.get") as mock_get,
        ):
            mock_get.side_effect = aiohttp.ClientError("HTTP error")

            with pytest.raises(AuthError, match="Failed to fetch GitHub user"):
                await get_github_user("gho_test123")


class TestAuthApiEndpoints:
    def test_github_login_redirects(self, mock_github_oauth_settings):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/github/login", follow_redirects=False)

        assert response.status_code == 307

    def test_github_callback_returns_422_without_code(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/github/callback")

        assert response.status_code == 422

    def test_get_me_returns_401_without_token(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/github/me")

        assert response.status_code == 401

    def test_logout_returns_message(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/v1/github/logout")

        assert response.status_code == 200
        assert response.json()["message"] == "Logged out"


class TestAuthServiceWithMocks:
    @pytest.fixture
    def mock_jwt_settings(self, jwt_settings):
        with patch("demetra.services.auth.JWT", jwt_settings):
            yield

    @pytest.mark.asyncio
    async def test_authenticate_user_creates_new_user(self, mock_jwt_settings):
        mock_github_user = GitHubUser(id="123", login="testuser", email="test@example.com")

        result = await authenticate_user(mock_github_user)

        assert result.token is not None
        assert result.user.id is not None
        assert result.user.github_username == "testuser"

    @pytest.mark.asyncio
    async def test_verify_jwt_token_returns_none_for_invalid_token(self, mock_jwt_settings):
        result = await verify_jwt_token("invalid_token")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_returns_none_without_token(self, mock_jwt_settings):
        result = await get_current_user("")
        assert result is None


class TestHasPermission:
    def test_admin_can_view_logs(self):
        user = UserResponse(id="1", github_username="admin", email="admin@test.com", role="admin")
        assert has_permission(user, "view_logs") is True

    def test_user_cannot_view_logs(self):
        user = UserResponse(id="2", github_username="user", email="user@test.com", role="user")
        assert has_permission(user, "view_logs") is False

    def test_dict_admin_can_view_logs(self):
        user = {"role": "admin"}
        assert has_permission(user, "view_logs") is True

    def test_dict_user_cannot_view_logs(self):
        user = {"role": "user"}
        assert has_permission(user, "view_logs") is False

    def test_unknown_permission_returns_false(self):
        user = UserResponse(id="1", github_username="admin", email="admin@test.com", role="admin")
        assert has_permission(user, "unknown_permission") is False


class TestSignupWithPassword:
    @pytest.mark.asyncio
    async def test_signup_creates_user_and_returns_auth_response(self, mock_jwt_settings):
        email = f"signup-test-{__import__('uuid').uuid4().hex[:8]}@example.com"
        result = await signup_with_password(email=email, password="hunter2hunter2")

        assert result.token is not None
        assert result.user.id is not None
        assert result.user.email == email
        assert result.user.github_username is None

    @pytest.mark.asyncio
    async def test_signup_rejects_email_when_allowlist_enforced(self, mock_jwt_settings, allowlist_seeded):
        email = f"blocked-{__import__('uuid').uuid4().hex[:8]}@example.com"

        with pytest.raises(AuthError, match="Email not authorized for registration"):
            await signup_with_password(email=email, password="hunter2hunter2")

    @pytest.mark.asyncio
    async def test_signup_raises_on_duplicate_email(self, mock_jwt_settings):
        email = f"dup-test-{__import__('uuid').uuid4().hex[:8]}@example.com"
        await signup_with_password(email=email, password="hunter2hunter2")

        with pytest.raises(AuthError, match="Email already registered"):
            await signup_with_password(email=email, password="anotherpass1")

    @pytest.mark.asyncio
    async def test_signup_raises_on_invalid_email(self, mock_jwt_settings):
        with pytest.raises(AuthError, match="Invalid email"):
            await signup_with_password(email="not-an-email", password="hunter2hunter2")


class TestLoginWithPassword:
    @pytest.mark.asyncio
    async def test_login_returns_auth_response(self, mock_jwt_settings):
        email = f"login-test-{__import__('uuid').uuid4().hex[:8]}@example.com"
        await signup_with_password(email=email, password="hunter2hunter2")

        result = await login_with_password(email=email, password="hunter2hunter2")

        assert result.token is not None
        assert result.user.id is not None
        assert result.user.email == email

    @pytest.mark.asyncio
    async def test_login_raises_on_wrong_password(self, mock_jwt_settings):
        email = f"wrong-pw-test-{__import__('uuid').uuid4().hex[:8]}@example.com"
        await signup_with_password(email=email, password="hunter2hunter2")

        with pytest.raises(AuthError, match="Invalid email or password"):
            await login_with_password(email=email, password="wrongPassword1")

    @pytest.mark.asyncio
    async def test_login_raises_on_unknown_email(self, mock_jwt_settings):
        with pytest.raises(AuthError, match="Invalid email or password"):
            await login_with_password(email="nonexistent@example.com", password="hunter2hunter2")
