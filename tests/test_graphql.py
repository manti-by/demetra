from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from demetra.library.exceptions import LinearError
from demetra.services.linear.graphql import get_query, graphql_request


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

    def _mock_session_with_responses(self, responses):
        """Build a session mock that answers with the given responses in order.

        Args:
            responses: The ``(status, headers, json)`` triples, one per call.

        Returns:
            AsyncMock: The session context manager mock.
        """
        post_context_managers = []
        for status, headers, json_value in responses:
            mock_response = AsyncMock()
            mock_response.status = status
            mock_response.headers = headers
            mock_response.raise_for_status = MagicMock(
                side_effect=aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=status)
                if status >= 400
                else None
            )
            mock_response.json = AsyncMock(return_value=json_value)

            mock_post_cm = AsyncMock()
            mock_post_cm.__aenter__.return_value = mock_response
            mock_post_cm.__aexit__.return_value = None
            post_context_managers.append(mock_post_cm)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(side_effect=post_context_managers)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None
        return mock_session_cm

    @pytest.mark.asyncio
    async def test_graphql_request_returns_dict_payload(self):
        with (
            patch("demetra.services.linear.graphql.get_valid_token", new_callable=AsyncMock) as mock_token,
            patch("demetra.services.linear.graphql.aiohttp.ClientSession") as mock_client_session,
        ):
            mock_token.return_value = "token"
            mock_client_session.return_value = self._mock_session({"data": {"issueUpdate": {"success": True}}})

            result = await graphql_request(query="query {}")

        assert result == {"data": {"issueUpdate": {"success": True}}}

    @pytest.mark.asyncio
    async def test_graphql_request_raises_linear_error_on_null_payload(self):
        with (
            patch("demetra.services.linear.graphql.get_valid_token", new_callable=AsyncMock) as mock_token,
            patch("demetra.services.linear.graphql.aiohttp.ClientSession") as mock_client_session,
        ):
            mock_token.return_value = "token"
            mock_client_session.return_value = self._mock_session(None)

            with pytest.raises(LinearError):
                await graphql_request(query="query {}")

    @pytest.mark.asyncio
    async def test_graphql_request_raises_linear_error_on_list_payload(self):
        with (
            patch("demetra.services.linear.graphql.get_valid_token", new_callable=AsyncMock) as mock_token,
            patch("demetra.services.linear.graphql.aiohttp.ClientSession") as mock_client_session,
        ):
            mock_token.return_value = "token"
            mock_client_session.return_value = self._mock_session([])

            with pytest.raises(LinearError):
                await graphql_request(query="query {}")

    @pytest.mark.asyncio
    async def test_graphql_request_retries_a_rate_limited_response(self):
        payload = {"data": {"issueUpdate": {"success": True}}}
        with (
            patch("demetra.services.linear.graphql.get_valid_token", new_callable=AsyncMock) as mock_token,
            patch("demetra.services.linear.graphql.aiohttp.ClientSession") as mock_client_session,
            patch("demetra.services.linear.graphql.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_token.return_value = "token"
            mock_client_session.return_value = self._mock_session_with_responses(
                [
                    (429, {"Retry-After": "2"}, None),
                    (200, {}, payload),
                ]
            )

            result = await graphql_request(query="query {}")

        assert result == payload
        mock_sleep.assert_awaited_once_with(2.0)

    @pytest.mark.asyncio
    async def test_graphql_request_gives_up_after_the_rate_limit_retries(self):
        with (
            patch("demetra.services.linear.graphql.get_valid_token", new_callable=AsyncMock) as mock_token,
            patch("demetra.services.linear.graphql.aiohttp.ClientSession") as mock_client_session,
            patch("demetra.services.linear.graphql.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_token.return_value = "token"
            mock_client_session.return_value = self._mock_session_with_responses(
                [(429, {"Retry-After": "1"}, None)] * 4
            )

            with pytest.raises(LinearError):
                await graphql_request(query="query {}")
