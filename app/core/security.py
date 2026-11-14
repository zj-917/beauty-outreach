"""Authentication and phone cryptography helpers."""

from __future__ import annotations

import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken


def verify_admin_token(provided: str | None, expected: str) -> bool:
    """Compare the admin token in constant time."""
    if provided is None:
        return False
    return hmac.compare_digest(provided, expected)


def sign_webhook_payload(secret: str, raw: bytes) -> str:
    """Return the ``sha256=<hex>`` signature over the raw request body."""
    digest = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_webhook_signature(secret: str, raw: bytes, header: str | None) -> bool:
    """Compare a webhook signature header against the raw body in constant time."""
    if not header:
        return False
    return hmac.compare_digest(header, sign_webhook_payload(secret, raw))


class PhoneCipher:
    """Encrypt and hash normalized phone numbers with configured keys."""

    def __init__(self, encryption_key: str, hash_key: str) -> None:
        self._fernet = Fernet(encryption_key.encode("utf-8"))
        self._hash_key = hash_key.encode("utf-8")

    def encrypt(self, e164: str) -> str:
        """Encrypt an E.164 number."""
        return self._fernet.encrypt(e164.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        """Decrypt an encrypted E.164 number."""
        return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")

    def try_decrypt(self, token: str) -> str | None:
        """Decrypt a token, returning None when it is malformed or unreadable."""
        try:
            return self.decrypt(token)
        except (InvalidToken, UnicodeError, ValueError):
            return None

    def hash_phone(self, e164: str) -> str:
        """Return the stable HMAC-SHA256 hex digest of an E.164 number."""
        return hmac.new(self._hash_key, e164.encode("utf-8"), hashlib.sha256).hexdigest()
