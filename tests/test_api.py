import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketDisconnect


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


class TestLinearService:
    @pytest.mark.asyncio
    async def test_create_linear_ticket_returns_ticket_info(
        self,
        mock_graphql_request: AsyncMock,
        linear_issue_id: str,
        linear_identifier: str,
    ):
        from demetra.services.linear import create_linear_ticket

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
        from demetra.library.exceptions import LinearError
        from demetra.services.linear import create_linear_ticket

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
    def test_create_ticket_returns_400_on_empty_text(self, auth_cookie: dict):
        from demetra.api import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/v1/tickets/", json={"text": "  "}, cookies=auth_cookie)

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
        auth_cookie: dict,
    ):
        from demetra.api import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/v1/tickets/", json={"text": "Add user auth"}, cookies=auth_cookie)

        assert response.status_code == 200
        assert response.json()["identifier"] == linear_identifier

    @pytest.mark.asyncio
    async def test_create_ticket_uses_custom_title(
        self,
        mock_groq: AsyncMock,
        mock_create_linear_ticket: AsyncMock,
        auth_cookie: dict,
    ):
        from demetra.api import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/v1/tickets/", json={"text": "Add user auth"}, cookies=auth_cookie)

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

        with patch("demetra.api.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises((WebSocketDisconnect, Exception)):
                with TestClient(app).websocket_connect(
                    "/api/v1/watcher/logs", cookies={"auth_token": "invalid_token"}
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
                with patch("demetra.api.get_current_user", new_callable=AsyncMock) as mock_get_user:
                    mock_get_user.return_value = {"id": "user-123", "github_username": "testuser", "role": "admin"}

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
            with patch("demetra.api.get_current_user", new_callable=AsyncMock) as mock_get_user:
                mock_get_user.return_value = {"id": "user-123", "github_username": "testuser"}

                with pytest.raises((WebSocketDisconnect, Exception)):
                    with TestClient(app).websocket_connect(
                        "/api/v1/watcher/logs", cookies={"auth_token": "valid_token"}
                    ) as _:
                        pass
