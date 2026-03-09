import json

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from demetra.settings import ENCRYPTION_SALT, SECRET_KEY


def _get_fernet() -> Fernet:
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY is not configured")
    salt = ENCRYPTION_SALT.encode() if ENCRYPTION_SALT else b"demetra_salt"
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
    key = kdf.derive(SECRET_KEY.encode())
    return Fernet(key)


def encrypt(data: dict) -> str:
    fernet = _get_fernet()
    json_data = json.dumps(data)
    encrypted = fernet.encrypt(json_data.encode())
    return encrypted.decode()


def decrypt(encrypted_data: str) -> dict:
    fernet = _get_fernet()
    decrypted = fernet.decrypt(encrypted_data.encode())
    return json.loads(decrypted.decode())
