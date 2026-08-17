from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.pagination import decode_cursor, encode_cursor


def test_cursor_round_trip() -> None:
    created_at = datetime(2026, 8, 17, 1, 2, 3, 456789, tzinfo=UTC)
    entity_id = uuid4()
    cursor = encode_cursor(created_at, entity_id)
    decoded = decode_cursor(cursor)
    assert decoded.created_at == created_at
    assert decoded.entity_id == entity_id


def test_invalid_cursor_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid pagination cursor"):
        decode_cursor("not-a-valid-cursor")
