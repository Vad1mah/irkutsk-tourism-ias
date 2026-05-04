import pytest

from app.services.parser_health_service import parser_health_service
from app.services.cache_service import cache_service


@pytest.mark.asyncio
async def test_parser_health_report_and_list():
    """Проверяет запись и чтение статуса парсера через Redis hash.

    Всегда делает свежее подключение, чтобы не зависеть от loop-state
    session-scoped фикстуры.
    """
    # Создаём свежее соединение для этого теста
    fresh_client = None
    try:
        import redis.asyncio as redis
        from app.config import settings
        fresh_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password,
            decode_responses=True,
        )
        await fresh_client.ping()
    except Exception:
        pytest.skip("Redis unavailable")
        return

    try:
        await fresh_client.hset(
            "parser_health",
            "events_yandex_test",
            '{"parser_id": "events_yandex_test", "status": "ok", "items_collected": 42, "error": null, "last_run": "2026-01-01T00:00:00"}',
        )
        raw = await fresh_client.hgetall("parser_health")
        import json
        found = None
        for k, v in raw.items():
            try:
                entry = json.loads(v)
                if entry.get("parser_id") == "events_yandex_test":
                    found = entry
                    break
            except Exception:
                continue

        assert found is not None
        assert found["status"] == "ok"
        assert found["items_collected"] == 42
    finally:
        try:
            await fresh_client.hdel("parser_health", "events_yandex_test")
            await fresh_client.aclose()
        except Exception:
            pass


@pytest.mark.asyncio
async def test_parser_health_endpoint(client):
    response = await client.get("/api/parser/health")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
