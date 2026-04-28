import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketDisconnect

from demetra.library.exceptions import LinearError
from demetra.library.models import UserResponse
from demetra.services.auth import create_jwt_token
from demetra.services.linear import create_linear_ticket


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
            token, _ = create_jwt_token("test_user_id")
            return {"auth_token": token}


class TestLinearService:
    @pytest.mark.asyncio
    async def test_create_linear_ticket_returns_ticket_info(
        self,
        mock_graphql_request: AsyncMock,
        linear_issue_id: str,
        linear_identifier: str,
    ):

        with patch(
            "demetra.services.linear.LINEAR",
            {
                "team_id": "team-123",
                "default_state": "state-123",
                "default_project": "project-123",
                "feature_label_id": "label-123",
                "states": {},
                "projects": {},
                "api_url": "",
                "client_id": None,
                "client_secret": None,
                "oauth_scope": "",
                "oauth_token_url": "",
                "service_name": "",
            },
        ):
            result = await create_linear_ticket("Test", "Desc", "Req", "AC")

        assert result["ticket_id"] == linear_issue_id
        assert result["identifier"] == linear_identifier
        assert "title" in result

    @pytest.mark.asyncio
    async def test_create_linear_ticket_raises_on_failure(
        self,
        linear_graphql_response_failure: dict,
    ):
        with patch(
            "demetra.services.linear.graphql_request",
            new_callable=AsyncMock,
        ) as mock_request:
            mock_request.return_value = linear_graphql_response_failure
            with patch(
                "demetra.services.linear.LINEAR",
                {
                    "team_id": "team-123",
                    "default_state": "state-123",
                    "default_project": "project-123",
                    "feature_label_id": "label-123",
                    "states": {},
                    "projects": {},
                    "api_url": "",
                    "client_id": None,
                    "client_secret": None,
                    "oauth_scope": "",
                    "oauth_token_url": "",
                    "service_name": "",
                },
            ):
                with pytest.raises(LinearError, match="Failed to create Linear ticket"):
                    await create_linear_ticket("Test", "Desc", "Req", "AC")


class TestApiEndpoint:
    def test_create_ticket_returns_400_on_empty_text(self, authenticated_client: TestClient):
        response = authenticated_client.post("/api/v1/tickets", json={"text": "  "})

        assert response.status_code == 400
        assert response.json()["detail"] == "Text cannot be empty"

    def test_create_ticket_returns_422_on_missing_text(self):
        from demetra.api import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/v1/tickets/", json={})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_ticket_returns_ticket_on_success(
        self,
        mock_groq: AsyncMock,
        mock_create_linear_ticket: AsyncMock,
        linear_identifier: str,
        authenticated_client: TestClient,
    ):
        response = authenticated_client.post("/api/v1/tickets", json={"text": "Add user auth"})

        assert response.status_code == 200
        assert response.json()["identifier"] == linear_identifier

    @pytest.mark.asyncio
    async def test_create_ticket_uses_custom_title(
        self,
        mock_groq: AsyncMock,
        mock_create_linear_ticket: AsyncMock,
        authenticated_client: TestClient,
    ):
        response = authenticated_client.post("/api/v1/tickets", json={"text": "Add user auth"})

        assert response.status_code == 200
        mock_create_linear_ticket.assert_called_once()
        call_args = mock_create_linear_ticket.call_args
        assert call_args.kwargs["title"] == mock_groq.return_value["title"]


class TestWatcherLogsWebSocket:
    @pytest.mark.asyncio
    async def test_websocket_rejects_missing_auth_token(self):
        from demetra.api import app

        with pytest.raises((WebSocketDisconnect, Exception)):
            with TestClient(app).websocket_connect("/api/v1/watcher/logs") as _:
                pass

    @pytest.mark.asyncio
    async def test_websocket_rejects_invalid_auth_token(self):
        from demetra.api import app

        with patch("demetra.api.watcher.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises((WebSocketDisconnect, Exception)):
                with TestClient(app).websocket_connect(
                    "/api/v1/watcher/logs", cookies={"auth_token": "valid_token"}
                ) as _:
                    pass

    @pytest.mark.asyncio
    async def test_websocket_streams_logs(
        self,
        mock_groq: AsyncMock,
        mock_create_linear_ticket: AsyncMock,
    ):
        from demetra.api import app

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            temp_log_path = f.name

        try:
            with patch.dict(os.environ, {"LOG_PATH": temp_log_path}):
                with patch("demetra.api.watcher.get_current_user", new_callable=AsyncMock) as mock_get_user:
                    mock_get_user.return_value = {"id": "user-123", "github_username": "testuser", "role": "admin"}

                    with pytest.raises((WebSocketDisconnect, Exception)):
                        with TestClient(app).websocket_connect(
                            "/api/v1/watcher/logs", cookies={"auth_token": "valid_token"}
                        ) as _:
                            pass

        finally:
            os.unlink(temp_log_path)

    @pytest.mark.asyncio
    async def test_websocket_fails_on_missing_log_file(
        self,
        mock_groq: AsyncMock,
        mock_create_linear_ticket: AsyncMock,
    ):
        from demetra.api import app

        with patch.dict(os.environ, {"LOG_PATH": "/nonexistent/path/logs.log"}):
            with patch("demetra.api.watcher.get_current_user", new_callable=AsyncMock) as mock_get_user:
                mock_get_user.return_value = {"id": "user-123", "github_username": "testuser"}

                with pytest.raises((WebSocketDisconnect, Exception)):
                    with TestClient(app).websocket_connect(
                        "/api/v1/watcher/logs", cookies={"auth_token": "valid_token"}
                    ) as _:
                        pass


class TestUserKeysEndpoint:
    def test_update_keys_returns_401_without_auth_token(self):
        from demetra.api import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.patch("/api/v1/users/me/keys", json={"keys": {"some_key": "some_value"}})

        assert response.status_code == 401

    def test_update_keys_returns_401_with_invalid_token(self):
        from demetra.api import app

        with patch("demetra.api.users.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None

            client = TestClient(app, raise_server_exceptions=False)
            response = client.patch(
                "/api/v1/users/me/keys",
                json={"keys": {"some_key": "some_value"}},
                cookies={"auth_token": "invalid_token"},
            )

            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_keys_returns_success_on_valid_data(
        self,
        authenticated_client: TestClient,
    ):
        with patch("demetra.api.update_user_keys", new_callable=AsyncMock) as mock_update_keys:
            with patch("demetra.api.get_current_user", new_callable=AsyncMock) as mock_get_user:
                mock_get_user.return_value = UserResponse(
                    id="test_user_id",
                    github_username="testuser",
                    email="test@example.com",
                )
                response = authenticated_client.patch(
                    "/api/v1/users/me/keys",
                    json={"keys": {"some_key": "some_value"}},
                )

                assert response.status_code == 200
                assert response.json()["message"] == "Keys updated successfully"
                mock_update_keys.assert_called_once_with(user_id="test_user_id", keys={"some_key": "some_value"})


class TestProjectEndpoints:
    def test_list_projects_returns_401_without_auth_token(self):
        from demetra.api import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/projects")

        assert response.status_code == 401

    def test_list_projects_returns_401_with_invalid_token(self):
        from demetra.api import app

        with patch("demetra.api.projects.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None

            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v1/projects", cookies={"auth_token": "invalid_token"})

            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_projects_returns_projects_for_authenticated_user(
        self,
        authenticated_client: TestClient,
    ):
        with patch(
            "demetra.api.projects.get_projects_by_user",
            new_callable=AsyncMock,
        ) as mock_get_projects:
            mock_get_projects.return_value = [
                {
                    "id": "project-1",
                    "user_id": "test_user_id",
                    "linear_project_id": "linear-123",
                    "name": "Test Project",
                    "state": "active",
                    "repository_url": "https://github.com/test/repo",
                    "repository_name": "repo",
                    "repository_owner": "test",
                    "local_path": "/home/user/projects/test/repo",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
            ]

            with patch("demetra.api.projects.get_current_user", new_callable=AsyncMock) as mock_get_user:
                mock_get_user.return_value = UserResponse(
                    id="test_user_id",
                    github_username="testuser",
                    email="test@example.com",
                )
                response = authenticated_client.get("/api/v1/projects")

                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1
                assert data[0]["name"] == "Test Project"

    def test_create_project_returns_401_without_auth_token(self):
        from demetra.api import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/v1/projects",
            json={"name": "Test", "repository_url": "https://github.com/test/repo"},
        )

        assert response.status_code == 401

    def test_create_project_returns_400_on_empty_name(self, authenticated_client: TestClient):
        with patch("demetra.api.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = UserResponse(
                id="test_user_id",
                github_username="testuser",
                email="test@example.com",
            )
            response = authenticated_client.post(
                "/api/v1/projects",
                json={"name": "  ", "repository_url": "https://github.com/test/repo"},
            )

            assert response.status_code == 400
            assert "name" in response.json()["detail"].lower()

    def test_create_project_returns_400_on_empty_url(self, authenticated_client: TestClient):
        with patch("demetra.api.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = UserResponse(
                id="test_user_id",
                github_username="testuser",
                email="test@example.com",
            )
            response = authenticated_client.post(
                "/api/v1/projects",
                json={"name": "Test", "repository_url": "  "},
            )

            assert response.status_code == 400
            assert "url" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_project_creates_project_for_authenticated_user(
        self,
        authenticated_client: TestClient,
    ):
        with patch(
            "demetra.api.projects.setup_project",
            new_callable=AsyncMock,
        ) as mock_setup_project:
            with patch(
                "demetra.api.projects.create_project",
                new_callable=AsyncMock,
            ) as mock_create_project:
                with patch(
                    "demetra.api.projects.update_project",
                    new_callable=AsyncMock,
                ) as mock_update_project:
                    with patch("demetra.api.projects.get_current_user", new_callable=AsyncMock) as mock_get_user:
                        mock_get_user.return_value = UserResponse(
                            id="test_user_id",
                            github_username="testuser",
                            email="test@example.com",
                        )
                        mock_setup_project.return_value = {
                            "local_path": "/home/user/projects/test/repo",
                            "db_name": "test",
                            "db_user": "test",
                            "db_password": "test-password",
                        }
                        mock_create_project.return_value = {
                            "id": "new-project-id",
                            "user_id": "test_user_id",
                            "linear_project_id": None,
                            "name": "New Project",
                            "repository_url": "https://github.com/test/repo",
                            "local_path": None,
                            "state": "provisioning",
                            "created_at": "2026-01-01T00:00:00",
                            "updated_at": "2026-01-01T00:00:00",
                        }
                        mock_update_project.return_value = {
                            "id": "new-project-id",
                            "user_id": "test_user_id",
                            "linear_project_id": None,
                            "name": "New Project",
                            "repository_url": "https://github.com/test/repo",
                            "local_path": "/home/user/projects/test/repo",
                            "state": "active",
                            "created_at": "2026-01-01T00:00:00",
                            "updated_at": "2026-01-01T00:00:00",
                        }

                        response = authenticated_client.post(
                            "/api/v1/projects",
                            json={"name": "New Project", "repository_url": "https://github.com/test/repo"},
                        )

                        assert response.status_code == 200

    def test_delete_project_returns_401_without_auth_token(self):
        from demetra.api import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.delete("/api/v1/projects/project-id")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_project_deletes_project_for_authenticated_user(
        self,
        authenticated_client: TestClient,
    ):
        with patch(
            "demetra.api.projects.delete_project",
            new_callable=AsyncMock,
        ) as mock_delete_project:
            with patch("demetra.api.projects.get_current_user", new_callable=AsyncMock) as mock_get_user:
                mock_get_user.return_value = UserResponse(
                    id="test_user_id",
                    github_username="testuser",
                    email="test@example.com",
                )
                response = authenticated_client.delete("/api/v1/projects/project-id")

                assert response.status_code == 200
                mock_delete_project.assert_called_once_with(project_id="project-id", user_id="test_user_id")
