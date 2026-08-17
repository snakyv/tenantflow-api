import pytest

from app.infra.rate_limit import check_rate_limit


class FakeRedis:
    def __init__(self, results: list[list[int]]) -> None:
        self.results = results

    async def eval(self, *_args: object) -> list[int]:
        return self.results.pop(0)


async def test_rate_limit_allows_request_with_remaining_capacity() -> None:
    result = await check_rate_limit(FakeRedis([[1, 8, 0]]), "key", limit=10, window_seconds=60)
    assert result.allowed
    assert result.remaining == 8
    assert result.retry_after == 0


async def test_rate_limit_rejects_over_limit() -> None:
    result = await check_rate_limit(FakeRedis([[0, 0, 6]]), "key", limit=10, window_seconds=60)
    assert not result.allowed
    assert result.remaining == 0
    assert result.retry_after == 6


@pytest.mark.parametrize(("limit", "window"), [(0, 60), (10, 0), (-1, 60)])
async def test_rate_limit_rejects_invalid_configuration(limit: int, window: int) -> None:
    with pytest.raises(ValueError):
        await check_rate_limit(FakeRedis([]), "key", limit=limit, window_seconds=window)
