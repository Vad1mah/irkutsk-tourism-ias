"""Тест на race condition счётчика SSE-стримов (баг C1)."""
import asyncio
import pytest
import pytest_asyncio
import redis.asyncio as aioredis

from app.config import settings
from app.routers.query import _STREAM_COUNTER_KEY


@pytest_asyncio.fixture
async def redis_client():
    """Прямое подключение к Redis в function-scope loop — не трогает глобальный cache_service."""
    client = aioredis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password,
        decode_responses=True,
    )
    await client.ping()
    await client.delete(_STREAM_COUNTER_KEY)
    yield client
    await client.delete(_STREAM_COUNTER_KEY)
    await client.aclose()


@pytest.mark.asyncio
async def test_concurrent_stream_increments_are_atomic(redis_client):
    """100 параллельных incrementов дают ровно +100 счётчику (Redis INCR атомарен)."""
    # Патчим cache_service.client на наш тестовый клиент
    from app.services.cache_service import cache_service
    original_client = cache_service._client
    original_connected = cache_service._connected
    cache_service._client = redis_client
    cache_service._connected = True

    from app.routers.query import increment_active_stream, decrement_active_stream, get_active_streams

    try:
        initial = await get_active_streams()
        await asyncio.gather(*(increment_active_stream() for _ in range(100)))
        after = await get_active_streams()
        assert after - initial == 100

        # Cleanup
        await asyncio.gather(*(decrement_active_stream() for _ in range(100)))
        after_decrement = await get_active_streams()
        assert after_decrement == initial, f"Counter not restored: {after_decrement} vs {initial}"
    finally:
        cache_service._client = original_client
        cache_service._connected = original_connected
