from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from demetra.app import app
from demetra.library.models import GitHubUser
from demetra.services.auth import (
    AuthError,
    authenticate_user,
    create_jwt_token,
    exchange_code_for_token,
    get_current_user,
    get_github_auth_url,
    verify_jwt_token,
)


class TestAuthService:
    @pytest.fixture
    def mock_github_oauth_no_credentials(self, github_oauth_settings):
        github_oauth_settings["client_id"] = None
        github_oauth_settings["client_secret"] = None
        with patch("demetra.services.auth.GITHUB_OAUTH", github_oauth_settings):
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
