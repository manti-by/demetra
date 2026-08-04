import base64
import json

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from demetra.settings import ENCRYPTION_SALT, SECRET_KEY


def get_fernet() -> Fernet:
    """Create a Fernet cipher derived from the app secret key.

    Derives a 32-byte key via PBKDF2-HMAC-SHA256 from the configured secret
    key and salt.

    Returns:
        Fernet: A configured Fernet instance for encrypting and decrypting.

    Raises:
        ValueError: When SECRET_KEY or ENCRYPTION_SALT is not configured.
    """
    if not SECRET_KEY or not ENCRYPTION_SALT:
        raise ValueError("SECRET_KEY and/or ENCRYPTION_SALT is not configured")

    salt = ENCRYPTION_SALT.encode()
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
    key = kdf.derive(SECRET_KEY.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(data: dict) -> str:
    """Encrypt a dict as a JSON Fernet token.

    Args:
        data: The mapping to serialize and encrypt.

    Returns:
        str: The encrypted token string.
    """
    fernet = get_fernet()
    json_data = json.dumps(data)
    encrypted = fernet.encrypt(json_data.encode())
    return encrypted.decode()


def decrypt(encrypted_data: str) -> dict:
    """Decrypt a Fernet token back into a dict.

    Args:
        encrypted_data: The encrypted token string.

    Returns:
        dict: The decrypted mapping.

    Raises:
        ValueError: When the token is invalid or corrupted.
    """
    try:
        fernet = get_fernet()
        decrypted = fernet.decrypt(encrypted_data.encode())
        return json.loads(decrypted.decode())
    except InvalidToken as e:
        raise ValueError("Failed to decrypt data: invalid or corrupted") from e


def encrypt_str(plaintext: str) -> str:
    """Encrypt a plain string into a Fernet token.

    Args:
        plaintext: The string to encrypt.

    Returns:
        str: The encrypted token string.
    """
    fernet = get_fernet()
    encrypted = fernet.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt_str(ciphertext: str) -> str:
    """Decrypt a Fernet token back into a plain string.

    Args:
        ciphertext: The encrypted token string.

    Returns:
        str: The decrypted string.

    Raises:
        ValueError: When the token is invalid or corrupted.
    """
    try:
        fernet = get_fernet()
        decrypted = fernet.decrypt(ciphertext.encode())
        return decrypted.decode()
    except InvalidToken as e:
        raise ValueError("Failed to decrypt data: invalid or corrupted") from e
