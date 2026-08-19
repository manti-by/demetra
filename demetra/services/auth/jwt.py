from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

import demetra.services.auth as service
from demetra.library.exceptions import AuthError
from demetra.library.models import TokenData


def create_jwt_token(user_id: str) -> tuple[str, str]:
    """Create a signed JWT for a user and its expiry timestamp.

    Args:
        user_id: The user id encoded in the token.

    Returns:
        tuple[str, str]: The JWT and its ISO-8601 expiry timestamp.

    Raises:
        AuthError: When no JWT secret key is configured.
    """
    if not service.JWT["secret_key"]:
        raise AuthError("JWT_SECRET_KEY must be set")

    expires_delta = timedelta(days=service.JWT["expiration_days"])
    expire = datetime.now(UTC) + expires_delta

    to_encode = {"user_id": user_id, "exp": int(expire.timestamp())}
    token = jwt.encode(to_encode, service.JWT["secret_key"], algorithm=service.JWT["algorithm"])

    return token, expire.isoformat()


async def verify_jwt_token(token: str) -> TokenData | None:
    """Validate a JWT against its signature, stored session and expiry.

    Args:
        token: The JWT to verify.

    Returns:
        TokenData | None: The token payload when valid, otherwise None.
    """
    if not service.JWT["secret_key"]:
        raise AuthError("JWT_SECRET_KEY must be set")

    try:
        payload = jwt.decode(token, service.JWT["secret_key"], algorithms=[service.JWT["algorithm"]])

        token_data = await service.get_jwt_token(token)
        if not token_data:
            return None

        user_data = await service.get_user_by_id(token_data["user_id"])
        if not user_data:
            return None

        if user_data.get("password_version", 1) != token_data.get("password_version", 1):
            return None

        expires_at = token_data["expires_at"]
        if expires_at is None or datetime.now(UTC) > expires_at:
            return None

        return TokenData(user_id=payload["user_id"], exp=payload["exp"])
    except JWTError:
        return None
