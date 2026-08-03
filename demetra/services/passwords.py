import bcrypt

from demetra.library.exceptions import AuthError


def hash_password(plain: str) -> str:
    _validate_password(plain=plain)
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain:
        return False
    try:
        _validate_password(plain=plain)
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except AuthError:
        return False


def _validate_password(plain: str) -> None:
    if not plain:
        raise AuthError("Password cannot be empty")

    if len(plain) < 8:
        raise AuthError("Password must be at least 8 characters long")

    if len(plain.encode("utf-8")) > 72:
        raise AuthError("Password must not exceed 72 bytes")
