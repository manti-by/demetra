import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketDisconnect

from demetra.app import app
from demetra.library.exceptions import LinearError
from demetra.library.models import SessionHistory
from demetra.services.linear import create_linear_ticket


class TestLinearService:
    @pytest.fixture
    def mock_linear_full(self, linear_full_settings):
        with patch("demetra.services.linear.LINEAR", linear_full_settings):
            yield

    @pytest.mark.asyncio
    async def test_create_linear_ticket_returns_ticket_info(
        self,
        mock_graphql_request: AsyncMock,
        mock_linear_full,
        linear_issue_id: str,
        linear_identifier: str,
    ):
        result = await create_linear_ticket("Test", "Desc", "Req", "AC")

        assert result["ticket_id"] == linear_issue_id
        assert result["identifier"] == linear_identifier
        assert "title" in result

    @pytest.mark.asyncio
    async def test_create_linear_ticket_raises_on_failure(
        self,
        mock_linear_full,
        linear_graphql_response_failure: dict,
    ):
        with patch(
            "demetra.services.linear.graphql_request",
            new_callable=AsyncMock,
        ) as mock_request:
            mock_request.return_value = linear_graphql_response_failure
            with pytest.raises(LinearError, match="Failed to create Linear ticket"):
                await create_linear_ticket("Test", "Desc", "Req", "AC")


class TestWatcherLogsWebSocket:
    WS_PATH = "/ws/v1/watcher/logs"
    TASK_ID = "00000000-0000-4000-8000-000000000001"

    @pytest.mark.asyncio
    async def test_websocket_rejects_missing_auth_token(self):
        with pytest.raises((WebSocketDisconnect, Exception)):
            with TestClient(app).websocket_connect(self.WS_PATH) as _:
                pass

    @pytest.mark.asyncio
    async def test_websocket_rejects_invalid_auth_token(self):
        with patch("demetra.api.watcher.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises((WebSocketDisconnect, Exception)):
                with TestClient(app).websocket_connect(
                    f"{self.WS_PATH}?task_id={self.TASK_ID}",
                    cookies={"auth_token": "valid_token"},
                ) as _:
                    pass

    @pytest.mark.asyncio
    async def test_websocket_emits_log_envelope(
        self,
        mock_groq: AsyncMock,
        mock_create_linear_ticket: AsyncMock,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            session_dir = log_dir / "sessions"
            session_dir.mkdir(parents=True, exist_ok=True)
            log_file = session_dir / f"{self.TASK_ID}.log"
            log_file.write_text("test log line\n")

            with (
                patch("demetra.api.watcher.LOG_DIR", log_dir),
                patch("demetra.api.watcher.get_current_user", new_callable=AsyncMock) as mock_get_user,
                patch("demetra.api.watcher.get_session_step_name", new_callable=AsyncMock) as mock_step,
            ):
                mock_get_user.return_value = {"id": "user-123", "github_username": "testuser", "role": "admin"}
                mock_step.return_value = ("initial", "Test Session")

                with TestClient(app).websocket_connect(
                    f"{self.WS_PATH}?task_id={self.TASK_ID}",
                    cookies={"auth_token": "valid_token"},
                ) as ws:
                    # First message should be initial status
                    status_msg = ws.receive_json()
                    assert status_msg["type"] == "status"
                    assert status_msg["data"]["step"] == "initial"
                    assert status_msg["data"]["name"] == "Test Session"

                    # Next should be the log line
                    log_msg = ws.receive_json()
                    assert log_msg["type"] == "log"
                    assert log_msg["data"]["text"] == "test log line"

    @pytest.mark.asyncio
    async def test_websocket_emits_status_on_step_change(
        self,
        mock_groq: AsyncMock,
        mock_create_linear_ticket: AsyncMock,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            session_dir = log_dir / "sessions"
            session_dir.mkdir(parents=True, exist_ok=True)
            log_file = session_dir / f"{self.TASK_ID}.log"
            log_file.touch()

            step_call_count = 0

            async def mock_step_side_effect(task_id: str):
                nonlocal step_call_count
                step_call_count += 1
                if step_call_count <= 2:
                    return ("initial", "Test Session")
                return ("build", "Test Session")

            with (
                patch("demetra.api.watcher.LOG_DIR", log_dir),
                patch("demetra.api.watcher.get_current_user", new_callable=AsyncMock) as mock_get_user,
                patch("demetra.api.watcher.get_session_step_name", new_callable=AsyncMock) as mock_step,
            ):
                mock_get_user.return_value = {"id": "user-123", "github_username": "testuser", "role": "admin"}
                mock_step.side_effect = mock_step_side_effect

                with TestClient(app).websocket_connect(
                    f"{self.WS_PATH}?task_id={self.TASK_ID}",
                    cookies={"auth_token": "valid_token"},
                ) as ws:
                    msg1 = ws.receive_json()
                    assert msg1["type"] == "status"
                    assert msg1["data"]["step"] == "initial"

                    # After polling, should see the step change
                    msg2 = ws.receive_json()
                    assert msg2["type"] == "status"
                    assert msg2["data"]["step"] == "build"

    @pytest.mark.asyncio
    async def test_websocket_closes_when_session_deleted(
        self,
        mock_groq: AsyncMock,
        mock_create_linear_ticket: AsyncMock,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            session_dir = log_dir / "sessions"
            session_dir.mkdir(parents=True, exist_ok=True)
            log_file = session_dir / f"{self.TASK_ID}.log"
            log_file.touch()

            step_call_count = 0

            async def mock_step_side_effect(task_id: str):
                nonlocal step_call_count
                step_call_count += 1
                if step_call_count <= 2:
                    return ("initial", "Test Session")
                return None

            with (
                patch("demetra.api.watcher.LOG_DIR", log_dir),
                patch("demetra.api.watcher.get_current_user", new_callable=AsyncMock) as mock_get_user,
                patch("demetra.api.watcher.get_session_step_name", new_callable=AsyncMock) as mock_step,
            ):
                mock_get_user.return_value = {"id": "user-123", "github_username": "testuser", "role": "admin"}
                mock_step.side_effect = mock_step_side_effect

                with TestClient(app).websocket_connect(
                    f"{self.WS_PATH}?task_id={self.TASK_ID}",
                    cookies={"auth_token": "valid_token"},
                ) as ws:
                    msg1 = ws.receive_json()
                    assert msg1["type"] == "status"
                    assert msg1["data"]["step"] == "initial"

                    msg2 = ws.receive_json()
                    assert msg2["type"] == "status"
                    assert msg2["data"]["step"] == "deleted"


class TestUserKeysEndpoint:
    def test_update_keys_returns_401_without_auth_token(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.patch("/api/v1/users/me/keys", json={"keys": {"some_key": "some_value"}})

        assert response.status_code == 401

    def test_update_keys_returns_401_with_invalid_token(self):
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
        with patch("demetra.api.users.update_user_keys", new_callable=AsyncMock) as mock_update_keys:
            response = authenticated_client.patch(
                "/api/v1/users/me/keys",
                json={"keys": {"some_key": "some_value"}},
            )

            assert response.status_code == 200
            assert response.json()["message"] == "Keys updated successfully"
            mock_update_keys.assert_called_once_with(user_id="test_user_id", keys={"some_key": "some_value"})


class TestProjectEndpoints:
    def test_list_projects_returns_401_without_auth_token(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/projects")

        assert response.status_code == 401

    def test_list_projects_returns_401_with_invalid_token(self):
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

            response = authenticated_client.get("/api/v1/projects")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "Test Project"

    def test_create_project_returns_401_without_auth_token(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/v1/projects",
            json={"name": "Test", "repository_url": "https://github.com/test/repo"},
        )

        assert response.status_code == 401

    def test_create_project_returns_400_on_empty_name(self, authenticated_client: TestClient):
        response = authenticated_client.post(
            "/api/v1/projects",
            json={"name": "  ", "repository_url": "https://github.com/test/repo"},
        )

        assert response.status_code == 400
        assert "name" in response.json()["detail"].lower()

    def test_create_project_returns_400_on_empty_url(self, authenticated_client: TestClient):
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
            response = authenticated_client.delete("/api/v1/projects/project-id")

            assert response.status_code == 200
            mock_delete_project.assert_called_once_with(project_id="project-id", user_id="test_user_id")


class TestProjectEnvironmentEndpoints:
    def test_list_environment_returns_401_without_auth_token(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/projects/project-id/environment")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_environment_returns_entries(
        self,
        authenticated_client: TestClient,
    ):
        with (
            patch(
                "demetra.api.projects.get_project_by_id",
                new_callable=AsyncMock,
                return_value={"id": "project-id"},
            ),
            patch(
                "demetra.api.projects.list_project_environments",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "id": "env-1",
                        "project_id": "project-id",
                        "key": "API_KEY",
                        "value": "secret",
                        "type": "text",
                    }
                ],
            ) as mock_list,
        ):
            response = authenticated_client.get("/api/v1/projects/project-id/environment")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["key"] == "API_KEY"
            assert data[0]["value"] == "secret"
            assert data[0]["type"] == "text"
            assert data[0]["project_id"] == "project-id"
            mock_list.assert_called_once_with(project_id="project-id", user_id="test_user_id")

    @pytest.mark.asyncio
    async def test_list_environment_masks_encrypted_values(
        self,
        authenticated_client: TestClient,
    ):
        with (
            patch(
                "demetra.api.projects.get_project_by_id",
                new_callable=AsyncMock,
                return_value={"id": "project-id"},
            ),
            patch(
                "demetra.api.projects.list_project_environments",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "id": "env-1",
                        "project_id": "project-id",
                        "key": "API_KEY",
                        "value": "********",
                        "type": "encrypted",
                    }
                ],
            ),
        ):
            response = authenticated_client.get("/api/v1/projects/project-id/environment")

            assert response.status_code == 200
            data = response.json()
            assert data[0]["value"] == "********"
            assert data[0]["type"] == "encrypted"

    @pytest.mark.asyncio
    async def test_list_environment_returns_404_for_missing_project(
        self,
        authenticated_client: TestClient,
    ):
        with patch(
            "demetra.api.projects.list_project_environments",
            new_callable=AsyncMock,
            side_effect=LookupError("missing"),
        ):
            response = authenticated_client.get("/api/v1/projects/project-id/environment")

            assert response.status_code == 404

    def test_upsert_environment_returns_401_without_auth_token(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.put(
            "/api/v1/projects/project-id/environment/API_KEY",
            json={"value": "secret"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_upsert_environment_creates_entry(
        self,
        authenticated_client: TestClient,
    ):
        with patch(
            "demetra.api.projects.upsert_project_environment",
            new_callable=AsyncMock,
            return_value={
                "id": "env-1",
                "project_id": "project-id",
                "key": "API_KEY",
                "value": "secret",
                "type": "text",
            },
        ) as mock_upsert:
            response = authenticated_client.put(
                "/api/v1/projects/project-id/environment/API_KEY",
                json={"value": "secret"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["key"] == "API_KEY"
            assert data["value"] == "secret"
            assert data["type"] == "text"
            mock_upsert.assert_called_once_with(
                project_id="project-id",
                user_id="test_user_id",
                key="API_KEY",
                value="secret",
                env_type="text",
            )

    @pytest.mark.asyncio
    async def test_upsert_environment_with_encrypted_type(
        self,
        authenticated_client: TestClient,
    ):
        with patch(
            "demetra.api.projects.upsert_project_environment",
            new_callable=AsyncMock,
            return_value={
                "id": "env-1",
                "project_id": "project-id",
                "key": "API_KEY",
                "value": "********",
                "type": "encrypted",
            },
        ) as mock_upsert:
            response = authenticated_client.put(
                "/api/v1/projects/project-id/environment/API_KEY",
                json={"value": "secret", "type": "encrypted"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["type"] == "encrypted"
            assert data["value"] == "********"
            mock_upsert.assert_called_once_with(
                project_id="project-id",
                user_id="test_user_id",
                key="API_KEY",
                value="secret",
                env_type="encrypted",
            )

    def test_upsert_environment_rejects_invalid_type(
        self,
        authenticated_client: TestClient,
    ):
        response = authenticated_client.put(
            "/api/v1/projects/project-id/environment/API_KEY",
            json={"value": "secret", "type": "binary"},
        )

        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_upsert_environment_returns_404_for_missing_project(
        self,
        authenticated_client: TestClient,
    ):
        with patch(
            "demetra.api.projects.upsert_project_environment",
            new_callable=AsyncMock,
            side_effect=LookupError("missing"),
        ):
            response = authenticated_client.put(
                "/api/v1/projects/project-id/environment/API_KEY",
                json={"value": "secret"},
            )

            assert response.status_code == 404

    def test_delete_environment_returns_401_without_auth_token(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.delete("/api/v1/projects/project-id/environment/API_KEY")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_environment_removes_entry(
        self,
        authenticated_client: TestClient,
    ):
        with patch(
            "demetra.api.projects.delete_project_environment",
            new_callable=AsyncMock,
        ) as mock_delete:
            response = authenticated_client.delete("/api/v1/projects/project-id/environment/API_KEY")

            assert response.status_code == 200
            assert response.json()["message"] == "Environment variable deleted successfully"
            mock_delete.assert_called_once_with(
                project_id="project-id",
                user_id="test_user_id",
                key="API_KEY",
            )

    @pytest.mark.asyncio
    async def test_delete_environment_returns_404_for_missing_project(
        self,
        authenticated_client: TestClient,
    ):
        with patch(
            "demetra.api.projects.delete_project_environment",
            new_callable=AsyncMock,
            side_effect=LookupError("missing"),
        ):
            response = authenticated_client.delete("/api/v1/projects/project-id/environment/API_KEY")

            assert response.status_code == 404


class TestSessionHistoryEndpoint:
    def test_returns_401_without_auth_token(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/sessions/TASK-123/history")
        assert response.status_code == 401

    def test_returns_401_with_invalid_token(self):
        with patch("demetra.api.sessions.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None

            client = TestClient(app, raise_server_exceptions=False)
            response = client.get(
                "/api/v1/sessions/TASK-123/history",
                cookies={"auth_token": "invalid_token"},
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_404_when_session_id_not_found(self, authenticated_client: TestClient):
        with patch(
            "demetra.api.sessions.get_session_id_by_task_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = authenticated_client.get("/api/v1/sessions/TASK-123/history")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_history_rows(self, authenticated_client: TestClient):
        mock_rows = [
            SessionHistory(
                id="h1",
                session_id="session-abc",
                step="plan",
                created_at="2026-01-01T00:00:00Z",
                length=1000,
                input_tokens=500,
                output_tokens=300,
                reasoning_tokens=100,
                cache_read_tokens=50,
                cache_write_tokens=50,
            ),
            SessionHistory(
                id="h2",
                session_id="session-abc",
                step="build",
                created_at="2026-01-01T01:00:00Z",
                length=2500,
                input_tokens=1200,
                output_tokens=800,
                reasoning_tokens=300,
                cache_read_tokens=100,
                cache_write_tokens=100,
            ),
        ]

        with (
            patch(
                "demetra.api.sessions.get_session_id_by_task_id",
                new_callable=AsyncMock,
                return_value="session-abc",
            ),
            patch(
                "demetra.api.sessions.get_session_history",
                new_callable=AsyncMock,
                return_value=mock_rows,
            ),
        ):
            response = authenticated_client.get("/api/v1/sessions/TASK-123/history")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["step"] == "plan"
            assert data[0]["input_tokens"] == 500
            assert data[0]["output_tokens"] == 300
            assert data[1]["step"] == "build"
            assert data[1]["input_tokens"] == 1200
