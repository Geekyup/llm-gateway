from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    settings = get_settings()
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_key(plaintext: str) -> str:
    """Encrypt a raw API key for storage. Returns a str safe for a text/String column."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_key(ciphertext: str) -> str:
    """Decrypt a stored API key. Only call this at the point of use (provider.forward)."""
    return _fernet().decrypt(ciphertext.encode()).decode()
