import aiohttp

from demetra.library.exceptions import LinearError
from demetra.services.persistence.database import get_oauth_token, save_oauth_token
from demetra.settings import LINEAR


async def get_valid_token() -> str:
    """Return a valid OAuth access token, refreshing it when expired.

    Returns a stored non-expired token when available, otherwise fetches a new
    one via client credentials.

    Returns:
        str: A valid access token.

    Raises:
        LinearError: When OAuth settings are missing or the fetch fails.
    """
    token_data = await get_oauth_token(LINEAR["service_name"])
    if token_data and token_data[0]:
        return token_data[0]

    if not LINEAR["client_id"] or not LINEAR["client_secret"]:
        raise LinearError("LINEAR_CLIENT_ID and LINEAR_CLIENT_SECRET must be set")

    token = await fetch_new_token()
    return token


async def fetch_new_token() -> str:
    """Fetch and persist a fresh OAuth access token via client credentials.

    Returns:
        str: The newly fetched access token.

    Raises:
        LinearError: When OAuth settings are missing, the response contains no
            token, or the request fails.
    """
    if not LINEAR["client_id"] or not LINEAR["client_secret"]:
        raise LinearError("LINEAR_CLIENT_ID and LINEAR_CLIENT_SECRET must be set")

    payload = {
        "grant_type": "client_credentials",
        "scope": LINEAR["oauth_scope"],
        "client_id": LINEAR["client_id"],
        "client_secret": LINEAR["client_secret"],
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                LINEAR["oauth_token_url"],
                data=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response.raise_for_status()
                data = await response.json()

        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expires_in = int(data.get("expires_in", 2591999))

        if not access_token:
            raise LinearError("No access token in OAuth response")

        await save_oauth_token(
            service=LINEAR["service_name"],
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )
        return access_token
    except aiohttp.ClientError as e:
        raise LinearError(f"OAuth token fetch error: {e}") from e
