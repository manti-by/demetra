from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from demetra.app import app
from demetra.services.persistence.database import (
    get_session,
    save_session,
    update_session_pr_link,
    upsert_pending_session,
)


class TestSessionDeletionAPI:
    @pytest.mark.asyncio
    async def test_delete_session_requires_auth(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.delete("/api/v1/sessions/task-123")
        assert response.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_test_db")
    async def test_delete_session_not_found(self, authenticated_client: TestClient):
        response = authenticated_client.delete("/api/v1/sessions/nonexistent-task")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_session_rejects_leading_dash_task_id(self, authenticated_client: TestClient):
        response = authenticated_client.delete("/api/v1/sessions/-leading-dash")
        assert response.status_code == 422

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_test_db")
    async def test_delete_session_accepts_chat_task_id(self, authenticated_client: TestClient):
        response = authenticated_client.delete("/api/v1/sessions/CH-999999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_test_db")
    async def test_delete_session_success(self, authenticated_client: TestClient):

        task_id = "task-123"
        await upsert_pending_session(
            task_id=task_id, session_id="sess-456", user_id="test_user_id", name="Test Session"
        )
        response = authenticated_client.delete(f"/api/v1/sessions/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_test_db")
    async def test_delete_session_calls_database_delete(self, authenticated_client: TestClient):

        task_id = "my-task-id"
        await upsert_pending_session(
            task_id=task_id, session_id="sess-789", user_id="test_user_id", name="Test Session"
        )
        authenticated_client.delete(f"/api/v1/sessions/{task_id}")
        assert await get_session(task_id) is None


class TestSessionListingAPI:
    @pytest.mark.asyncio
    async def test_list_sessions_requires_auth(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/sessions")
        assert response.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_test_db")
    async def test_list_sessions_returns_sessions(self, authenticated_client: TestClient):
        response = authenticated_client.get("/api/v1/sessions")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_sessions_filter_by_step(self, authenticated_client: TestClient):
        with patch("demetra.api.sessions.get_sessions", new_callable=AsyncMock) as mock_get_sessions:
            mock_get_sessions.return_value = []
            response = authenticated_client.get("/api/v1/sessions?step=build")
            assert response.status_code == 200
            mock_get_sessions.assert_called_once_with(user_id="test_user_id", step="build", tag=None)

    @pytest.mark.asyncio
    async def test_list_sessions_filter_by_validate_step(self, authenticated_client: TestClient):
        with patch("demetra.api.sessions.get_sessions", new_callable=AsyncMock) as mock_get_sessions:
            mock_get_sessions.return_value = []
            response = authenticated_client.get("/api/v1/sessions?step=validate")
            assert response.status_code == 200
            mock_get_sessions.assert_called_once_with(user_id="test_user_id", step="validate", tag=None)

    @pytest.mark.asyncio
    async def test_list_sessions_invalid_step(self, authenticated_client: TestClient):
        response = authenticated_client.get("/api/v1/sessions?step=invalid")
        assert response.status_code == 400

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_test_db")
    async def test_list_sessions_returns_raw_session_data(self, authenticated_client: TestClient):

        task_id = f"task-{uuid4().hex[:8]}"
        await upsert_pending_session(
            task_id=task_id, session_id="session-456", user_id="test_user_id", name="Test Session"
        )
        response = authenticated_client.get("/api/v1/sessions")
        assert response.status_code == 200
        data = response.json()
        session = next(s for s in data if s["task_id"] == task_id)
        assert session["session_id"] == "session-456"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_test_db")
    async def test_list_sessions_includes_name_field(self, authenticated_client: TestClient):

        task_id = f"task-{uuid4().hex[:8]}"
        await upsert_pending_session(
            task_id=task_id,
            session_id="session-name-test",
            user_id="test_user_id",
            name="DEMETRA-1: Add user authentication",
        )
        response = authenticated_client.get("/api/v1/sessions")
        assert response.status_code == 200
        data = response.json()
        session = next(s for s in data if s["task_id"] == task_id)
        assert session["name"] == "DEMETRA-1: Add user authentication"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_test_db")
    async def test_list_sessions_name_is_null_when_not_set(self, authenticated_client: TestClient):

        task_id = f"task-{uuid4().hex[:8]}"
        await upsert_pending_session(
            task_id=task_id,
            session_id="session-null-name",
            user_id="test_user_id",
        )
        response = authenticated_client.get("/api/v1/sessions")
        assert response.status_code == 200
        data = response.json()
        session = next(s for s in data if s["task_id"] == task_id)
        assert session["name"] == ""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_test_db")
    async def test_list_sessions_includes_pr_link_and_build_plan(self, authenticated_client: TestClient):

        task_id = f"task-{uuid4().hex[:8]}"
        await upsert_pending_session(
            task_id=task_id, session_id="session-pr-link", user_id="test_user_id", name="DEMETRA-1: Add user auth"
        )
        await save_session(
            task_id=task_id,
            build_plan="1. Step one\n2. Step two",
            name="DEMETRA-1: Add user auth",
            session_id="session-pr-link",
        )
        await update_session_pr_link(task_id, "https://github.com/owner/repo/pull/42")
        response = authenticated_client.get("/api/v1/sessions")
        assert response.status_code == 200
        data = response.json()
        session = next(s for s in data if s["task_id"] == task_id)
        assert session["build_plan"] == "1. Step one\n2. Step two"
        assert session["pr_link"] == "https://github.com/owner/repo/pull/42"


class TestLiveSessionsAPI:
    @pytest.mark.asyncio
    async def test_live_sessions_require_auth(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/sessions/live")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_live_sessions_returns_an_empty_list_when_nothing_runs(self, authenticated_client: TestClient):
        with (
            patch("demetra.api.sessions.get_live_task_ids", return_value=[]),
            patch("demetra.api.sessions.get_user_session_task_ids", new_callable=AsyncMock) as mock_owned,
        ):
            response = authenticated_client.get("/api/v1/sessions/live")

        assert response.status_code == 200
        assert response.json() == []
        mock_owned.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_test_db")
    async def test_live_sessions_returns_the_users_running_sessions(self, authenticated_client: TestClient):
        task_id = f"task-{uuid4().hex[:8]}"
        await upsert_pending_session(
            task_id=task_id, session_id="session-live", user_id="test_user_id", name="Live Session"
        )

        with patch("demetra.api.sessions.get_live_task_ids", return_value=[task_id]):
            response = authenticated_client.get("/api/v1/sessions/live")

        assert response.status_code == 200
        assert response.json() == [task_id]

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("setup_test_db")
    async def test_live_sessions_excludes_other_users_and_unknown_sessions(self, authenticated_client: TestClient):
        task_id = f"task-{uuid4().hex[:8]}"
        foreign_task_id = f"task-{uuid4().hex[:8]}"
        await upsert_pending_session(
            task_id=task_id, session_id="session-live", user_id="test_user_id", name="Live Session"
        )
        await upsert_pending_session(
            task_id=foreign_task_id, session_id="session-foreign", user_id="other_user_id", name="Foreign Session"
        )

        with patch(
            "demetra.api.sessions.get_live_task_ids",
            return_value=[task_id, foreign_task_id, "task-without-session"],
        ):
            response = authenticated_client.get("/api/v1/sessions/live")

        assert response.status_code == 200
        assert response.json() == [task_id]

    @pytest.mark.asyncio
    async def test_live_sessions_scopes_only_the_running_ids(self, authenticated_client: TestClient):
        # The ownership lookup is bounded by the running jobs, so the live ids
        # are passed straight through to the query instead of scanning every
        # session of the user.
        with (
            patch("demetra.api.sessions.get_live_task_ids", return_value=["CH-1", "CH-2"]),
            patch(
                "demetra.api.sessions.get_user_session_task_ids",
                new_callable=AsyncMock,
                return_value={"CH-2"},
            ) as mock_owned,
        ):
            response = authenticated_client.get("/api/v1/sessions/live")

        assert response.status_code == 200
        assert response.json() == ["CH-2"]
        mock_owned.assert_awaited_once_with(user_id="test_user_id", task_ids=["CH-1", "CH-2"])
