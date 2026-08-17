from uuid import uuid4

import pytest

from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    token_fingerprint,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    password = "correct horse battery staple"
    password_hash = hash_password(password)
    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_access_token_round_trip() -> None:
    user_id = uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id


def test_invalid_access_token_rejected() -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token("not-a-jwt")


def test_refresh_fingerprint_is_deterministic_and_non_plaintext() -> None:
    raw = "refresh-secret"
    fingerprint = token_fingerprint(raw)
    assert fingerprint == token_fingerprint(raw)
    assert fingerprint != raw
    assert len(fingerprint) == 64
