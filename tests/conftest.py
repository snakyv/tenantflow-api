import os
from collections.abc import AsyncIterator

import pytest

# Tests must never inherit APP_ENV=development/production from a local .env.
# This also makes SQLAlchemy use NullPool, which is safe across pytest-asyncio
# per-test event loops when integration tests share the cached AsyncEngine.
os.environ["APP_ENV"] = "test"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip infrastructure-dependent tests unless the caller explicitly enables them."""
    del config
    if os.getenv("RUN_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(
        reason="set RUN_INTEGRATION=1 with PostgreSQL/Redis infrastructure running"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
async def isolate_integration_redis(request: pytest.FixtureRequest) -> AsyncIterator[None]:
    """Prevent rate-limit/job state from leaking between infrastructure tests."""
    if "integration" not in request.keywords or os.getenv("RUN_INTEGRATION") != "1":
        yield
        return

    from app.infra.redis import get_redis

    client = await get_redis()
    try:
        await client.flushdb()
    finally:
        await client.aclose()

    yield
