import secrets

import aiohttp

import demetra.services.auth as service
from demetra.library.exceptions import AuthError
from demetra.library.models import GitHubUser


def get_github_auth_url() -> tuple[str, str]:
    """Build the GitHub OAuth authorization URL with a fresh state token.

    Returns:
        tuple[str, str]: The authorization URL and the state value to verify
            the callback against.
    """
    state = secrets.token_urlsafe(32)
    oauth = service.GITHUB["oauth"]
    params = {
        "client_id": oauth["client_id"],
        "redirect_uri": oauth["redirect_uri"],
        "scope": "read:user user:email",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{oauth['oauth_url']}?{query}", state


async def exchange_code_for_token(code: str) -> str:
    """Exchange an OAuth authorization code for a GitHub access token.

    Args:
        code: The authorization code from the GitHub callback.

    Returns:
        str: The GitHub access token.

    Raises:
        AuthError: When OAuth settings are missing or the exchange fails.
    """
    oauth = service.GITHUB["oauth"]
    if not oauth["client_id"] or not oauth["client_secret"]:
        raise AuthError("GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET must be set")

    payload = {
        "client_id": oauth["client_id"],
        "client_secret": oauth["client_secret"],
        "code": code,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                oauth["token_url"],
                data=payload,
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Accept": "application/json"},
            ) as response:
                response.raise_for_status()
                data = await response.json()

        access_token = data.get("access_token")
        if not access_token:
            raise AuthError("No access token in OAuth response")

        return access_token
    except aiohttp.ClientError as e:
        raise AuthError(f"OAuth token exchange error: {e}") from e


async def get_github_user(access_token: str) -> GitHubUser:
    """Fetch the authenticated GitHub user profile with an access token.

    Args:
        access_token: A valid GitHub access token.

    Returns:
        GitHubUser: The GitHub user identity.

    Raises:
        AuthError: When the GitHub API request fails.
    """
    oauth = service.GITHUB["oauth"]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                oauth["user_url"],
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Authorization": f"Bearer {access_token}"},
            ) as response:
                response.raise_for_status()
                data = await response.json()

        return GitHubUser(
            id=str(data["id"]),
            login=data["login"],
            email=data.get("email"),
            avatar_url=data.get("avatar_url"),
        )
    except aiohttp.ClientError as e:
        raise AuthError(f"Failed to fetch GitHub user: {e}") from e
