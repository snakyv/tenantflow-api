import uuid

import pytest

from app.infra.rate_limit import check_rate_limit
from app.infra.redis import get_redis

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_distributed_rate_limit_returns_429_ready_state() -> None:
    redis = await get_redis()
    key = f"test:ratelimit:{uuid.uuid4()}"
    try:
        first = await check_rate_limit(redis, key, limit=2, window_seconds=30)
        second = await check_rate_limit(redis, key, limit=2, window_seconds=30)
        third = await check_rate_limit(redis, key, limit=2, window_seconds=30)
        assert first.allowed and second.allowed
        assert not third.allowed
        assert third.remaining == 0
        assert third.retry_after > 0
    finally:
        await redis.delete(key)
        await redis.aclose()
