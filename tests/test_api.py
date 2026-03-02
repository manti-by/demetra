from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class TestLinearService:
    @pytest.mark.asyncio
    async def test_create_linear_ticket_returns_ticket_info(
        self,
        mock_graphql_request: AsyncMock,
        mock_linear_settings: None,
        linear_issue_id: str,
        linear_identifier: str,
    ):
        from demetra.services.linear import create_linear_ticket

        result = await create_linear_ticket("Test", "Desc", "Req", "AC")

        assert result["ticket_id"] == linear_issue_id
        assert result["identifier"] == linear_identifier
        assert "title" in result

    @pytest.mark.asyncio
    async def test_create_linear_ticket_raises_on_failure(
        self,
        linear_graphql_response_failure: dict,
        mock_linear_settings: None,
    ):
        from demetra.exceptions import LinearError
        from demetra.services.linear import create_linear_ticket

        with patch(
            "demetra.services.linear.graphql_request_with_api_key",
            new_callable=AsyncMock,
        ) as mock_request:
            mock_request.return_value = linear_graphql_response_failure
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
    async def test_create_ticket_returns_ticket_on_success(
        self,
        mock_groq: AsyncMock,
        mock_create_linear_ticket: AsyncMock,
        linear_identifier: str,
    ):
        from demetra.api import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/v1/tickets/", json={"text": "Add user auth"})

        assert response.status_code == 200
        assert response.json()["identifier"] == linear_identifier

    @pytest.mark.asyncio
    async def test_create_ticket_uses_custom_title(
        self,
        mock_groq: AsyncMock,
        mock_create_linear_ticket: AsyncMock,
    ):
        from demetra.api import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/v1/tickets/", json={"text": "Add user auth"})

        assert response.status_code == 200
        mock_create_linear_ticket.assert_called_once()
        call_args = mock_create_linear_ticket.call_args
        assert call_args.kwargs["title"] == mock_groq.return_value["title"]
