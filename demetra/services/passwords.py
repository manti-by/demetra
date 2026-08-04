import bcrypt

from demetra.library.exceptions import AuthError


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt.

    Args:
        plain: The plaintext password.

    Returns:
        str: The bcrypt hash as an ASCII string.

    Raises:
        AuthError: When the password fails validation.
    """
    _validate_password(plain=plain)
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Args:
        plain: The plaintext password.
        hashed: The stored bcrypt hash.

    Returns:
        bool: True when the password matches the hash.
    """
    if not plain:
        return False
    try:
        _validate_password(plain=plain)
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except (AuthError, UnicodeEncodeError, ValueError):
        return False


def _validate_password(plain: str) -> None:
    """Validate password length constraints for bcrypt compatibility.

    Enforces a minimum of 8 characters and a maximum of 72 bytes.

    Args:
        plain: The plaintext password.

    Raises:
        AuthError: When the password is empty, too short or too long.
    """
    if not plain:
        raise AuthError("Password cannot be empty")

    if len(plain) < 8:
        raise AuthError("Password must be at least 8 characters long")

    if len(plain.encode("utf-8")) > 72:
        raise AuthError("Password must not exceed 72 bytes")
