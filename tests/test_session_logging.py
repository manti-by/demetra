from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from demetra.app import app
from demetra.library.models import UserResponse


class TestSessionListingAPI:
    @pytest.mark.asyncio
    async def test_list_sessions_requires_auth(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/sessions")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_sessions_returns_sessions(self, authenticated_client: TestClient):
        with patch("demetra.api.sessions.get_sessions", new_callable=AsyncMock) as mock_get_sessions:
            mock_get_sessions.return_value = []

            with patch("demetra.api.sessions.get_current_user", new_callable=AsyncMock) as mock_get_user:
                mock_get_user.return_value = UserResponse(
                    id="user-123",
                    github_username="testuser",
                    email="test@example.com",
                    role="admin",
                )
                response = authenticated_client.get("/api/v1/sessions")
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_sessions_filter_by_status(self, authenticated_client: TestClient):
        with patch("demetra.api.sessions.get_sessions", new_callable=AsyncMock) as mock_get_sessions:
            mock_get_sessions.return_value = []

            with patch("demetra.api.sessions.get_current_user", new_callable=AsyncMock) as mock_get_user:
                mock_get_user.return_value = UserResponse(
                    id="user-123",
                    github_username="testuser",
                    email="test@example.com",
                    role="admin",
                )
                response = authenticated_client.get("/api/v1/sessions?status=pending")
                assert response.status_code == 200
                mock_get_sessions.assert_called_once_with(user_id="user-123", status="pending")

    @pytest.mark.asyncio
    async def test_list_sessions_invalid_status(self, authenticated_client: TestClient):
        with patch("demetra.api.sessions.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = UserResponse(
                id="user-123",
                github_username="testuser",
                email="test@example.com",
                role="admin",
            )
            response = authenticated_client.get("/api/v1/sessions?status=invalid")
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_sessions_returns_raw_session_data(self, authenticated_client: TestClient):
        with patch("demetra.api.sessions.get_sessions", new_callable=AsyncMock) as mock_get_sessions:
            mock_get_sessions.return_value = [
                {
                    "task_id": "task-123",
                    "session_id": "session-456",
                    "build_plan": "",
                    "posted_to_linear": True,
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "status": "pending",
                }
            ]

            with patch("demetra.api.sessions.get_current_user", new_callable=AsyncMock) as mock_get_user:
                mock_get_user.return_value = UserResponse(
                    id="user-123",
                    github_username="testuser",
                    email="test@example.com",
                    role="admin",
                )
                response = authenticated_client.get("/api/v1/sessions")
                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1
                assert data[0]["task_id"] == "task-123"
                assert data[0]["session_id"] == "session-456"
                assert data[0]["status"] == "pending"
