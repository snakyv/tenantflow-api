from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Cursor:
    created_at: datetime
    entity_id: UUID


def encode_cursor(created_at: datetime, entity_id: UUID) -> str:
    payload = json.dumps(
        {"created_at": created_at.isoformat(), "id": str(entity_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(value: str) -> Cursor:
    try:
        padded = value + "=" * (-len(value) % 4)
        raw = base64.urlsafe_b64decode(padded.encode())
        data = json.loads(raw)
        created_at = datetime.fromisoformat(data["created_at"])
        entity_id = UUID(data["id"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid pagination cursor") from exc
    if created_at.tzinfo is None:
        raise ValueError("Pagination cursor timestamp must be timezone-aware")
    return Cursor(created_at=created_at, entity_id=entity_id)
