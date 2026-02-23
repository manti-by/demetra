import aiohttp

from demetra.exceptions import LinearError
from demetra.services.database import get_oauth_token, save_oauth_token
from demetra.settings import LINEAR_CLIENT_ID, LINEAR_CLIENT_SECRET, LINEAR_OAUTH_SCOPE

LINEAR_OAUTH_TOKEN_URL = "https://api.linear.app/oauth/token"
LINEAR_SERVICE_NAME = "linear"


async def get_valid_token() -> str:
    token_data = await get_oauth_token(LINEAR_SERVICE_NAME)
    if token_data:
        return token_data[0]

    if not LINEAR_CLIENT_ID or not LINEAR_CLIENT_SECRET:
        raise LinearError("LINEAR_CLIENT_ID and LINEAR_CLIENT_SECRET must be set")

    token = await fetch_new_token()
    return token


async def fetch_new_token() -> str:
    if not LINEAR_CLIENT_ID or not LINEAR_CLIENT_SECRET:
        raise LinearError("LINEAR_CLIENT_ID and LINEAR_CLIENT_SECRET must be set")

    payload = {
        "grant_type": "client_credentials",
        "scope": LINEAR_OAUTH_SCOPE,
        "client_id": LINEAR_CLIENT_ID,
        "client_secret": LINEAR_CLIENT_SECRET,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                LINEAR_OAUTH_TOKEN_URL,
                data=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response.raise_for_status()
                data = await response.json()

        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expires_in = data.get("expires_in", 2591999)

        if not access_token:
            raise LinearError("No access token in OAuth response")

        await save_oauth_token(LINEAR_SERVICE_NAME, access_token, refresh_token, expires_in)
        return access_token
    except aiohttp.ClientError as e:
        raise LinearError(f"OAuth token fetch error: {e}") from e
