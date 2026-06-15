from unittest.mock import AsyncMock, patch

import pytest

from demetra.library.exceptions import LinearError
from demetra.services.oauth import get_valid_token


class TestOAuthService:
    @pytest.fixture
    def mock_get_oauth_token(self):
        with patch(
            "demetra.services.oauth.get_oauth_token",
            new_callable=AsyncMock,
        ) as mock:
            yield mock

    @pytest.fixture
    def mock_linear_config_with_creds(self):
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
            yield

    @pytest.fixture
    def mock_linear_config_without_creds(self):
        with patch(
            "demetra.services.oauth.LINEAR",
            {
                "client_id": None,
                "client_secret": None,
                "service_name": "test",
            },
        ):
            yield

    @pytest.fixture
    def mock_fetch_new_token(self):
        with patch(
            "demetra.services.oauth.fetch_new_token",
            new_callable=AsyncMock,
            return_value="new_token",
        ):
            yield

    @pytest.mark.asyncio
    async def test_get_valid_token_from_cache(self, mock_get_oauth_token):
        mock_get_oauth_token.return_value = ("cached_token",)
        result = await get_valid_token()
        assert result == "cached_token"

    @pytest.mark.asyncio
    async def test_get_valid_token_fetches_new(
        self,
        mock_get_oauth_token,
        mock_linear_config_with_creds,
        mock_fetch_new_token,
    ):
        mock_get_oauth_token.return_value = None
        result = await get_valid_token()
        assert result == "new_token"

    @pytest.mark.asyncio
    async def test_get_valid_token_missing_credentials(
        self,
        mock_get_oauth_token,
        mock_linear_config_without_creds,
    ):
        mock_get_oauth_token.return_value = None
        with pytest.raises(LinearError):
            await get_valid_token()
