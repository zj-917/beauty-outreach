"""Phone encryption and hashing tests."""

from __future__ import annotations

import hashlib
import hmac

import pytest
from cryptography.fernet import InvalidToken

from app.core.security import PhoneCipher

KEY = "ZmDfcTF7_60GrrY167zsiPd67pEvs0ouEkuFfKjGmS0="
OTHER_KEY = "cw_0x689RpI-jtRR7oE8h_eQsKImvJapLeSbXpwF4e4="
HASH_KEY = "test-phone-hash-key"


def test_AC_LEAD_008_phone_cipher_round_trip_and_stable_hash() -> None:
    """Given a normalized number, when encrypted and hashed, then both are reversible/stable."""
    cipher = PhoneCipher(KEY, HASH_KEY)
    token = cipher.encrypt("+15555550101")
    assert token != "+15555550101"
    assert cipher.decrypt(token) == "+15555550101"
    expected = hmac.new(HASH_KEY.encode(), b"+15555550101", hashlib.sha256).hexdigest()
    assert cipher.hash_phone("+15555550101") == expected
    assert cipher.hash_phone("+15555550101") == cipher.hash_phone("+15555550101")
    assert cipher.hash_phone("+15555550102") != expected


def test_AC_LEAD_008_phone_cipher_rejects_wrong_key() -> None:
    """Given ciphertext from one key, when decrypted with another key, then it raises."""
    token = PhoneCipher(KEY, HASH_KEY).encrypt("+15555550101")
    with pytest.raises(InvalidToken):
        PhoneCipher(OTHER_KEY, HASH_KEY).decrypt(token)


def test_AC_LEAD_008_phone_cipher_rejects_invalid_fernet_key() -> None:
    """Given an invalid Fernet key, when constructing the cipher, then it raises."""
    with pytest.raises(ValueError):
        PhoneCipher("not-a-fernet-key", HASH_KEY)
