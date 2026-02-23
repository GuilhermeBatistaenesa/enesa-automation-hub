from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

settings = get_settings()


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    key = settings.encryption_key.strip() if settings.encryption_key else ""
    if not key:
        raise ValueError("ENCRYPTION_KEY is not configured.")
    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("ENCRYPTION_KEY must be a valid Fernet key.") from exc


def encrypt_value(value: str) -> str:
    token = _get_fernet().encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(value_encrypted: str) -> str:
    try:
        plain = _get_fernet().decrypt(value_encrypted.encode("utf-8"))
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt secret value.") from exc
    return plain.decode("utf-8")
