import os
import tempfile
from pathlib import Path
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


class TestSessionLogging:
    def test_get_session_log_path_with_task_id(self):
        from demetra.services.session_logging import get_session_log_path

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("demetra.services.session_logging.LOG_DIR", Path(tmpdir)):
                log_path = get_session_log_path("DEMETRA-123")
                assert log_path.name == "DEMETRA-123.log"
                assert log_path.parent == Path(tmpdir)

    def test_get_session_log_path_without_task_id(self):
        from demetra.services.session_logging import get_session_log_path

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("demetra.services.session_logging.LOG_DIR", Path(tmpdir)):
                log_path = get_session_log_path(None)
                assert log_path.name.startswith("tmp-")
                assert log_path.name.endswith(".log")
                assert log_path.parent == Path(tmpdir)

    def test_rename_temp_log(self):
        from demetra.services.session_logging import get_session_log_path, rename_temp_log

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("demetra.services.session_logging.LOG_DIR", Path(tmpdir)):
                temp_log_path = get_session_log_path(None)
                temp_log_path.write_text("test content")

                new_path = rename_temp_log(temp_log_path, "DEMETRA-456")

                assert new_path.name == "DEMETRA-456.log"
                assert not temp_log_path.exists()
                assert new_path.exists()
                assert new_path.read_text() == "test content"

    def test_rename_temp_log_nonexistent_file(self):
        from demetra.services.session_logging import get_session_log_path, rename_temp_log

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("demetra.services.session_logging.LOG_DIR", Path(tmpdir)):
                temp_log_path = get_session_log_path(None)
                new_path = rename_temp_log(temp_log_path, "DEMETRA-456")

                assert new_path.name == "DEMETRA-456.log"

    def test_get_log_path_by_task_id_existing(self):
        from demetra.services.session_logging import get_log_path_by_task_id, get_session_log_path

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("demetra.services.session_logging.LOG_DIR", Path(tmpdir)):
                log_path = get_session_log_path("DEMETRA-789")
                log_path.write_text("test")

                result = get_log_path_by_task_id("DEMETRA-789")
                assert result == log_path

    def test_get_log_path_by_task_id_not_existing(self):
        from demetra.services.session_logging import get_log_path_by_task_id

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("demetra.services.session_logging.LOG_DIR", Path(tmpdir)):
                result = get_log_path_by_task_id("DEMETRA-999")
                assert result is None

    def test_different_tickets_have_separate_log_files(self):
        from demetra.services.session_logging import get_session_log_path

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("demetra.services.session_logging.LOG_DIR", Path(tmpdir)):
                log_path_1 = get_session_log_path("DEMETRA-100")
                log_path_2 = get_session_log_path("DEMETRA-200")
                log_path_3 = get_session_log_path("DEMETRA-300")

                log_path_1.write_text("log for ticket 100")
                log_path_2.write_text("log for ticket 200")
                log_path_3.write_text("log for ticket 300")

                assert log_path_1.read_text() == "log for ticket 100"
                assert log_path_2.read_text() == "log for ticket 200"
                assert log_path_3.read_text() == "log for ticket 300"
                assert log_path_1 != log_path_2
                assert log_path_2 != log_path_3


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

        with patch("demetra.services.database.get_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchall.return_value = []
            mock_connection.execute.return_value = mock_cursor
            mock_connection.__aenter__ = AsyncMock(return_value=mock_connection)
            mock_connection.__aexit__ = AsyncMock(return_value=None)
            mock_conn.return_value = mock_connection

            with patch("demetra.api.get_current_user", new_callable=AsyncMock) as mock_get_user:
                mock_get_user.return_value = {
                    "id": "user-123",
                    "github_username": "testuser",
                    "role": "admin",
                }

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


class TestWebSocketSessionLogging:
    @pytest.mark.asyncio
    async def test_websocket_with_session_id(self, auth_cookie: dict):
        from demetra.api import app

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write("test log content\n")
            temp_log_path = f.name

        try:
            with patch.dict(os.environ, {"LOG_PATH": temp_log_path}):
                with patch("demetra.api.get_current_user", new_callable=AsyncMock) as mock_get_user:
                    mock_get_user.return_value = {
                        "id": "user-123",
                        "github_username": "testuser",
                        "role": "admin",
                    }

                    with patch("demetra.api.get_log_path_by_task_id") as mock_get_path:
                        from pathlib import Path

                        mock_get_path.return_value = Path(temp_log_path)

                        from fastapi.testclient import TestClient
                        from starlette.testclient import WebSocketDisconnect

                        with pytest.raises((WebSocketDisconnect, Exception)):
                            with TestClient(app).websocket_connect(
                                "/api/v1/watcher/logs?session_id=DEMETRA-123", cookies=auth_cookie
                            ) as _:
                                pass

        finally:
            os.unlink(temp_log_path)

    @pytest.mark.asyncio
    async def test_websocket_session_not_found(self, auth_cookie: dict):
        from demetra.api import app

        with patch("demetra.api.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = {
                "id": "user-123",
                "github_username": "testuser",
                "role": "admin",
            }

            with patch("demetra.api.get_log_path_by_task_id") as mock_get_path:
                mock_get_path.return_value = None

                from fastapi.testclient import TestClient
                from starlette.testclient import WebSocketDisconnect

                with pytest.raises((WebSocketDisconnect, Exception)):
                    with TestClient(app).websocket_connect(
                        "/api/v1/watcher/logs?session_id=DEMETRA-999", cookies=auth_cookie
                    ) as _:
                        pass
