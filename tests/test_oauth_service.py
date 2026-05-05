from unittest.mock import AsyncMock, patch

import pytest

from demetra.library.exceptions import LinearError
from demetra.services.oauth import get_valid_token


class TestOAuthService:
    @pytest.mark.asyncio
    async def test_get_valid_token_from_cache(self):
        with patch(
            "demetra.services.oauth.get_oauth_token",
            new_callable=AsyncMock,
            return_value=("cached_token",),
        ):
            result = await get_valid_token()
            assert result == "cached_token"

    @pytest.mark.asyncio
    async def test_get_valid_token_fetches_new(self):
        with patch(
            "demetra.services.oauth.get_oauth_token",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with patch(
                "demetra.services.oauth.LINEAR",
                {
                    "client_id": "test_id",
                    "client_secret": "test_secret",
                    "oauth_scope": "test_scope",
                    "oauth_token_url": "https://test.com",
                    "service_name": "linear",
                },
            ):
                with patch(
                    "demetra.services.oauth.fetch_new_token",
                    new_callable=AsyncMock,
                    return_value="new_token",
                ):
                    result = await get_valid_token()
                    assert result == "new_token"

    @pytest.mark.asyncio
    async def test_get_valid_token_missing_credentials(self):
        with patch(
            "demetra.services.oauth.get_oauth_token",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with patch(
                "demetra.services.oauth.LINEAR",
                {
                    "client_id": None,
                    "client_secret": None,
                    "service_name": "test",
                },
            ):
                with pytest.raises(LinearError):
                    await get_valid_token()
