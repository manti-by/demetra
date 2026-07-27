import pytest

from demetra.services.auth import AuthError
from demetra.services.passwords import hash_password, verify_password


class TestHashPassword:
    def test_hash_returns_bcrypt_string(self):
        hashed = hash_password("hunter2hunter2")
        assert hashed.startswith("$2b$")

    def test_hash_produces_different_salts(self):
        h1 = hash_password("hunter2hunter2")
        h2 = hash_password("hunter2hunter2")
        assert h1 != h2

    def test_verify_accepts_correct_password(self):
        hashed = hash_password("hunter2hunter2")
        assert verify_password("hunter2hunter2", hashed) is True

    def test_verify_rejects_wrong_password(self):
        hashed = hash_password("hunter2hunter2")
        assert verify_password("wrongpassword", hashed) is False

    def test_rejects_empty(self):
        with pytest.raises(AuthError, match="Password cannot be empty"):
            hash_password("")

    def test_rejects_short(self):
        with pytest.raises(AuthError, match="Password must be at least 8 characters long"):
            hash_password("ab7" * 2)

    def test_rejects_too_long(self):
        with pytest.raises(AuthError, match="Password must not exceed 72 bytes"):
            hash_password("x" * 73)

    def test_accepts_exactly_72_bytes(self):
        hashed = hash_password("x" * 72)
        assert hashed.startswith("$2b$")

    def test_verify_rejects_empty(self):
        assert verify_password("", "$2b$12$abc") is False
