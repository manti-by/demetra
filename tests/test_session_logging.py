from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth_cookie() -> dict:
    with patch(
        "demetra.services.auth.JWT",
        {
            "secret_key": "test_secret_key",
            "algorithm": "HS256",
            "expiration_days": 14,
        },
    ):
        with patch(
            "demetra.services.auth.get_jwt_token",
            new_callable=AsyncMock,
            return_value={
                "token": "test_token",
                "user_id": "test_user_id",
                "expires_at": "2099-01-01T00:00:00+00:00",
            },
        ):
            from demetra.services.auth import create_jwt_token

            token, _ = create_jwt_token("test_user_id")
            return {"auth_token": token}


class TestSessionListingAPI:
    @pytest.mark.asyncio
    async def test_list_sessions_requires_auth(self):
        from demetra.api import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/sessions")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_sessions_returns_sessions(self, auth_cookie: dict):
        from demetra.api import app

        with patch("demetra.api.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = {
                "id": "user-123",
                "github_username": "testuser",
                "role": "admin",
            }

            with patch("demetra.api.get_sessions", new_callable=AsyncMock) as mock_get_sessions:
                mock_get_sessions.return_value = []

                client = TestClient(app, raise_server_exceptions=False)
                response = client.get("/api/v1/sessions", cookies=auth_cookie)
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_sessions_filter_by_status(self, auth_cookie: dict):
        from demetra.api import app

        with patch("demetra.api.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = {
                "id": "user-123",
                "github_username": "testuser",
                "role": "admin",
            }

            with patch("demetra.api.get_sessions", new_callable=AsyncMock) as mock_get_sessions:
                mock_get_sessions.return_value = []

                client = TestClient(app, raise_server_exceptions=False)
                response = client.get("/api/v1/sessions?status=pending", cookies=auth_cookie)
                assert response.status_code == 200
                mock_get_sessions.assert_called_once_with("pending")

    @pytest.mark.asyncio
    async def test_list_sessions_invalid_status(self, auth_cookie: dict):
        from demetra.api import app

        with patch("demetra.api.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = {
                "id": "user-123",
                "github_username": "testuser",
                "role": "admin",
            }

            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v1/sessions?status=invalid", cookies=auth_cookie)
            assert response.status_code == 400
