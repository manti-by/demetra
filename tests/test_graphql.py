from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from demetra.library.exceptions import LinearError
from demetra.services.graphql import get_query, graphql_request


class TestGraphqlService:
    @pytest.mark.asyncio
    async def test_get_todo_issues_query_returns_query_string(self):
        result = await get_query(name="get_all_issues")
        assert isinstance(result, str)
        assert "issues" in result.lower()
        assert "comments" in result.lower()


class TestGraphqlRequest:
    """Linear can respond 200 OK with a non-dict JSON body (e.g. `null`). Callers like
    update_ticket_status/post_comment do `result.get(...)` and previously crashed with an
    uncaught AttributeError in that case. graphql_request must reject it as a LinearError
    instead, so callers in main.py's except DemetraError handler can catch it gracefully."""

    def _mock_session(self, json_return_value):
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=json_return_value)

        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__.return_value = mock_response
        mock_post_cm.__aexit__.return_value = None

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_post_cm)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None
        return mock_session_cm

    @pytest.mark.asyncio
    async def test_graphql_request_returns_dict_payload(self):
        with (
            patch("demetra.services.graphql.get_valid_token", new_callable=AsyncMock) as mock_token,
            patch("demetra.services.graphql.aiohttp.ClientSession") as mock_client_session,
        ):
            mock_token.return_value = "token"
            mock_client_session.return_value = self._mock_session({"data": {"issueUpdate": {"success": True}}})

            result = await graphql_request(query="query {}")

        assert result == {"data": {"issueUpdate": {"success": True}}}

    @pytest.mark.asyncio
    async def test_graphql_request_raises_linear_error_on_null_payload(self):
        with (
            patch("demetra.services.graphql.get_valid_token", new_callable=AsyncMock) as mock_token,
            patch("demetra.services.graphql.aiohttp.ClientSession") as mock_client_session,
        ):
            mock_token.return_value = "token"
            mock_client_session.return_value = self._mock_session(None)

            with pytest.raises(LinearError):
                await graphql_request(query="query {}")

    @pytest.mark.asyncio
    async def test_graphql_request_raises_linear_error_on_list_payload(self):
        with (
            patch("demetra.services.graphql.get_valid_token", new_callable=AsyncMock) as mock_token,
            patch("demetra.services.graphql.aiohttp.ClientSession") as mock_client_session,
        ):
            mock_token.return_value = "token"
            mock_client_session.return_value = self._mock_session([])

            with pytest.raises(LinearError):
                await graphql_request(query="query {}")
