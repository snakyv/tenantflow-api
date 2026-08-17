from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models import IdempotencyRecord


@dataclass(slots=True)
class IdempotencyState:
    record: IdempotencyRecord
    replay_status: int | None = None
    replay_body: dict[str, Any] | None = None

    @property
    def is_replay(self) -> bool:
        return self.replay_status is not None


async def acquire_idempotency(
    session: AsyncSession,
    *,
    user_id: UUID,
    organization_id: UUID | None,
    scope: str,
    key: str,
    request_hash: str,
    ttl_hours: int = 24,
) -> IdempotencyState:
    now = datetime.now(UTC)
    statement = (
        insert(IdempotencyRecord)
        .values(
            user_id=user_id,
            organization_id=organization_id,
            scope=scope,
            key=key,
            request_hash=request_hash,
            status="processing",
            created_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
        )
        .on_conflict_do_nothing(index_elements=["scope", "key"])
        .returning(IdempotencyRecord.id)
    )
    created_id = await session.scalar(statement)
    if created_id is not None:
        record = await session.get(IdempotencyRecord, created_id)
        if record is None:
            raise RuntimeError("Newly created idempotency record could not be loaded")
        return IdempotencyState(record=record)

    record = await session.scalar(
        select(IdempotencyRecord)
        .where(IdempotencyRecord.scope == scope, IdempotencyRecord.key == key)
        .with_for_update()
    )
    if record is None:
        raise RuntimeError("Idempotency record disappeared after unique-key conflict")
    if record.request_hash != request_hash:
        raise ConflictError(
            "IDEMPOTENCY_KEY_REUSED",
            "Idempotency-Key was already used with a different request payload",
        )
    if record.status == "completed" and record.response_status is not None and record.response_body is not None:
        return IdempotencyState(
            record=record,
            replay_status=record.response_status,
            replay_body=record.response_body,
        )
    raise ConflictError("IDEMPOTENCY_IN_PROGRESS", "A request with this Idempotency-Key is in progress")


async def complete_idempotency(
    session: AsyncSession,
    record: IdempotencyRecord,
    *,
    status_code: int,
    response_body: dict[str, Any],
) -> None:
    record.status = "completed"
    record.response_status = status_code
    record.response_body = response_body
    await session.flush()
