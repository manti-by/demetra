from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class TestLinearService:
    @pytest.mark.asyncio
    async def test_create_linear_ticket_returns_ticket_info(self):
        from demetra.services.linear import create_linear_ticket

        mock_data = {
            "data": {
                "issueCreate": {
                    "success": True,
                    "issue": {
                        "id": "issue-123",
                        "identifier": "DEMETRA-42",
                        "title": "Test Ticket",
                    },
                }
            }
        }

        with patch("demetra.services.linear.graphql_request_with_api_key", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data
            with patch("demetra.services.linear.LINEAR_TEAM_ID", "team-123"):
                with patch("demetra.services.linear.LINEAR_STATE_TODO_ID", "state-todo"):
                    result = await create_linear_ticket("Test", "Desc", "Req", "AC")

        assert result["ticket_id"] == "issue-123"
        assert result["identifier"] == "DEMETRA-42"
        assert result["title"] == "Test Ticket"

    @pytest.mark.asyncio
    async def test_create_linear_ticket_raises_on_failure(self):
        from demetra.exceptions import LinearError
        from demetra.services.linear import create_linear_ticket

        mock_data = {
            "data": {
                "issueCreate": {
                    "success": False,
                }
            }
        }

        with patch("demetra.services.linear.graphql_request_with_api_key", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data
            with patch("demetra.services.linear.LINEAR_TEAM_ID", "team-123"):
                with patch("demetra.services.linear.LINEAR_STATE_TODO_ID", "state-todo"):
                    with pytest.raises(LinearError, match="Failed to create Linear ticket"):
                        await create_linear_ticket("Test", "Desc", "Req", "AC")


class TestApiEndpoint:
    def test_create_ticket_returns_400_on_empty_text(self):
        from demetra.api import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/v1/tickets/", json={"text": "  "})

        assert response.status_code == 400
        assert response.json()["detail"] == "Text cannot be empty"

    def test_create_ticket_returns_422_on_missing_text(self):
        from demetra.api import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/v1/tickets/", json={})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_ticket_returns_ticket_on_success(self):
        from demetra.api import app

        mock_ticket = {
            "ticket_id": "issue-123",
            "identifier": "DEMETRA-42",
            "title": "Test Ticket",
        }

        with patch("demetra.api.process_text_with_groq", new_callable=AsyncMock) as mock_groq:
            mock_groq.return_value = {
                "title": "Test",
                "description": "Desc",
                "tech_requirements": "Req",
                "acceptance_criteria": "AC",
                "project_name": "demetra",
            }
            with patch("demetra.api.create_linear_ticket", new_callable=AsyncMock) as mock_ticket_func:
                mock_ticket_func.return_value = mock_ticket

                client = TestClient(app, raise_server_exceptions=False)
                response = client.post("/api/v1/tickets/", json={"text": "Add user auth"})

        assert response.status_code == 200
        assert response.json()["identifier"] == "DEMETRA-42"

    @pytest.mark.asyncio
    async def test_create_ticket_uses_custom_title(self):
        from demetra.api import app

        mock_ticket = {
            "ticket_id": "issue-123",
            "identifier": "DEMETRA-42",
            "title": "Add user auth",
        }

        with patch("demetra.api.process_text_with_groq", new_callable=AsyncMock) as mock_groq:
            mock_groq.return_value = {
                "title": "AI Title",
                "description": "Desc",
                "tech_requirements": "Req",
                "acceptance_criteria": "AC",
                "project_name": "demetra",
            }
            with patch("demetra.api.create_linear_ticket", new_callable=AsyncMock) as mock_ticket_func:
                mock_ticket_func.return_value = mock_ticket

                client = TestClient(app, raise_server_exceptions=False)
                response = client.post("/api/v1/tickets/", json={"text": "Add user auth"})

        assert response.status_code == 200
        mock_ticket_func.assert_called_once()
        call_args = mock_ticket_func.call_args
        assert call_args.kwargs["title"] == "AI Title"
