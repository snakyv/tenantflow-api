from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class RedisEvalClient(Protocol):
    async def eval(self, script: str, numkeys: int, *keys_and_args: object) -> Sequence[object]: ...


def _redis_int(value: object) -> int:
    if isinstance(value, (int, str, bytes, bytearray)):
        return int(value)
    raise TypeError(f"Unexpected Redis Lua result type: {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int


# Distributed token bucket. Redis TIME provides a shared clock and the complete read/refill/consume
# transition runs atomically in one Lua script, so multiple API replicas enforce the same quota.
RATE_LIMIT_LUA = """
local capacity = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2]) * 1000
local time = redis.call('TIME')
local now_ms = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)
local state = redis.call('HMGET', KEYS[1], 'tokens', 'updated_at_ms')
local tokens = tonumber(state[1])
local updated_at_ms = tonumber(state[2])

if tokens == nil then
  tokens = capacity
  updated_at_ms = now_ms
end

local refill_per_ms = capacity / window_ms
local elapsed_ms = math.max(0, now_ms - updated_at_ms)
tokens = math.min(capacity, tokens + elapsed_ms * refill_per_ms)

local allowed = 0
local retry_after = 0
if tokens >= 1 then
  allowed = 1
  tokens = tokens - 1
else
  retry_after = math.ceil((1 - tokens) / refill_per_ms / 1000)
end

redis.call('HSET', KEYS[1], 'tokens', tokens, 'updated_at_ms', now_ms)
redis.call('PEXPIRE', KEYS[1], math.max(window_ms * 2, 1000))
return {allowed, math.floor(tokens), retry_after}
"""


async def check_rate_limit(
    redis: RedisEvalClient,
    key: str,
    limit: int,
    window_seconds: int,
) -> RateLimitResult:
    if limit <= 0 or window_seconds <= 0:
        raise ValueError("Rate-limit capacity and window must be positive")
    result = await redis.eval(RATE_LIMIT_LUA, 1, key, limit, window_seconds)
    allowed, remaining, retry_after = (
        _redis_int(result[0]),
        _redis_int(result[1]),
        _redis_int(result[2]),
    )
    return RateLimitResult(
        allowed=bool(allowed),
        remaining=max(0, remaining),
        retry_after=max(0, retry_after),
    )
