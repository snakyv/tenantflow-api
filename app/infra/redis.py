from typing import Any

from app.core.config import get_settings


async def get_redis() -> Any:
    from redis.asyncio import Redis

    return Redis.from_url(get_settings().redis_url, decode_responses=True)
