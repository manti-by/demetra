from unittest.mock import AsyncMock, call, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from demetra.app import app
from demetra.library.models import UserResponse
from demetra.services.auth import get_current_user_dep


class TestGetCurrentUserDep:
    @pytest.mark.asyncio
    async def test_raises_401_without_token(self):
        with patch("demetra.services.auth.get_current_user", new_callable=AsyncMock) as mock_get_user:
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_dep(auth_token=None)
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Not authenticated"
            mock_get_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_401_with_invalid_token(self):
        with patch("demetra.services.auth.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_dep(auth_token="invalid_token")
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Invalid token"
            mock_get_user.assert_called_once_with(token="invalid_token")


class TestCrossUserIsolation:
    def test_cannot_get_others_project(self, cross_user_client: TestClient):
        with patch(
            "demetra.api.projects.get_project_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_get_project:
            response = cross_user_client.get("/api/v1/projects/owner-project")

            assert response.status_code == 404
            mock_get_project.assert_called_once_with(project_id="owner-project", user_id="other_user_id")

    def test_cannot_delete_others_project(self, cross_user_client: TestClient):
        with patch(
            "demetra.api.projects.delete_project",
            new_callable=AsyncMock,
            return_value=False,
        ) as mock_delete_project:
            response = cross_user_client.delete("/api/v1/projects/owner-project")

            assert response.status_code == 404
            mock_delete_project.assert_called_once_with(project_id="owner-project", user_id="other_user_id")

    def test_cannot_list_others_environment(self, cross_user_client: TestClient):
        with patch(
            "demetra.api.projects.list_project_environments",
            new_callable=AsyncMock,
            side_effect=LookupError("Project not found"),
        ) as mock_list:
            response = cross_user_client.get("/api/v1/projects/owner-project/environment")

            assert response.status_code == 404
            mock_list.assert_called_once_with(project_id="owner-project", user_id="other_user_id")

    def test_cannot_upsert_others_environment(self, cross_user_client: TestClient):
        with patch(
            "demetra.api.projects.upsert_project_environment",
            new_callable=AsyncMock,
            side_effect=LookupError("Project not found"),
        ) as mock_upsert:
            response = cross_user_client.put(
                "/api/v1/projects/owner-project/environment/API_KEY",
                json={"value": "secret"},
            )

            assert response.status_code == 404
            mock_upsert.assert_called_once_with(
                project_id="owner-project",
                user_id="other_user_id",
                key="API_KEY",
                value="secret",
                env_type="text",
            )

    def test_cannot_get_others_session_history(self, cross_user_client: TestClient):
        with patch(
            "demetra.api.sessions.get_session_id_by_task_id",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_get_session_id:
            response = cross_user_client.get("/api/v1/sessions/OWNER-123/history")

            assert response.status_code == 404
            mock_get_session_id.assert_called_once_with(task_id="OWNER-123", user_id="other_user_id")

    def test_cannot_delete_others_session(self, cross_user_client: TestClient):
        with patch(
            "demetra.api.sessions.delete_session",
            new_callable=AsyncMock,
            return_value=False,
        ) as mock_delete_session:
            response = cross_user_client.delete("/api/v1/sessions/OWNER-123")

            assert response.status_code == 404
            mock_delete_session.assert_called_once_with(task_id="OWNER-123", user_id="other_user_id")

    def test_cannot_update_others_keys(self, cross_user_client: TestClient):
        with patch(
            "demetra.api.users.update_user_keys",
            new_callable=AsyncMock,
        ) as mock_update_keys:
            response = cross_user_client.patch(
                "/api/v1/users/me/keys",
                json={"keys": {"some_key": "some_value"}},
            )

            assert response.status_code == 200
            mock_update_keys.assert_called_once_with(user_id="other_user_id", keys={"some_key": "some_value"})


class TestWatcherWebSocketOwnership:
    WS_PATH = "/ws/v1/watcher/logs"
    TASK_ID = "00000000-0000-4000-8000-000000000002"

    @pytest.mark.asyncio
    async def test_websocket_rejects_task_owned_by_another_user(self):
        with (
            patch("demetra.api.watcher.get_current_user", new_callable=AsyncMock) as mock_get_user,
            patch("demetra.api.watcher.get_session_step_name", new_callable=AsyncMock) as mock_step,
        ):
            mock_get_user.return_value = UserResponse(id="user-123", github_username="testuser", role="admin")
            mock_step.side_effect = [None, ("initial", "Other User Session")]

            with TestClient(app).websocket_connect(
                f"{self.WS_PATH}?task_id={self.TASK_ID}",
                cookies={"auth_token": "valid_token"},
            ) as ws:
                message = ws.receive()
                assert message["type"] == "websocket.close"
                assert message["code"] == 4004

            mock_step.assert_has_awaits(
                [
                    call(task_id=self.TASK_ID, user_id="user-123"),
                    call(task_id=self.TASK_ID),
                ]
            )

    @pytest.mark.asyncio
    async def test_websocket_passes_user_id_to_step_lookup(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            session_dir = log_dir / "sessions"
            session_dir.mkdir(parents=True, exist_ok=True)
            log_file = session_dir / f"{self.TASK_ID}.log"
            log_file.touch()

            with (
                patch("demetra.api.watcher.LOG_DIR", log_dir),
                patch("demetra.api.watcher.get_current_user", new_callable=AsyncMock) as mock_get_user,
                patch("demetra.api.watcher.get_session_step_name", new_callable=AsyncMock) as mock_step,
            ):
                mock_get_user.return_value = UserResponse(id="user-123", github_username="testuser", role="admin")
                mock_step.return_value = ("initial", "Test Session")

                with TestClient(app).websocket_connect(
                    f"{self.WS_PATH}?task_id={self.TASK_ID}",
                    cookies={"auth_token": "valid_token"},
                ) as ws:
                    status_msg = ws.receive_json()
                    assert status_msg["type"] == "status"
                    assert status_msg["data"]["step"] == "initial"

                mock_step.assert_called_with(task_id=self.TASK_ID, user_id="user-123")
