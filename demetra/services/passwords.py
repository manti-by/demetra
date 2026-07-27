from passlib.context import CryptContext

from demetra.library.exceptions import AuthError


_PCTX = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    _validate_password(plain)
    return _PCTX.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    if not plain:
        return False
    return _PCTX.verify(plain, hashed)


def _validate_password(plain: str) -> None:
    if not plain:
        raise AuthError("Password cannot be empty")

    if len(plain) < 8:
        raise AuthError("Password must be at least 8 characters long")

    if len(plain.encode("utf-8")) > 72:
        raise AuthError("Password must not exceed 72 bytes")
