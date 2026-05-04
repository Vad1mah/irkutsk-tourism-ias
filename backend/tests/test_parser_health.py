import pytest

from app.services.parser_health_service import parser_health_service
from app.services.cache_service import cache_service


@pytest.mark.asyncio
async def test_parser_health_report_and_list():
    """Проверяет запись и чтение статуса парсера через ParserHealthService."""
    # Всегда пересоздаём соединение, чтобы не зависеть от loop-state
    # предыдущих тестов (cache_service — singleton, может быть poisoned).
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

    # Подменяем клиент в singleton для этого теста
    old_client = cache_service._client
    old_connected = cache_service._connected
    cache_service._client = fresh_client
    cache_service._connected = True

    parser_id = "test_health_parser"

    try:
        await parser_health_service.report(
            parser_id=parser_id,
            status="ok",
            items_collected=42,
        )

        entries = await parser_health_service.list_all()
        found = next((e for e in entries if e.get("parser_id") == parser_id), None)

        assert found is not None, "Запись не найдена в list_all()"
        assert found["status"] == "ok"
        assert found["items_collected"] == 42
        assert found["error"] is None
        assert "last_run" in found
    finally:
        try:
            await fresh_client.hdel("parser_health", parser_id)
            await fresh_client.aclose()
        except Exception:
            pass
        # Восстанавливаем предыдущее состояние singleton
        cache_service._client = old_client
        cache_service._connected = old_connected


@pytest.mark.asyncio
async def test_parser_health_sanitize_error():
    """Проверяет, что sanitize_error редактирует credentials из строки ошибки."""
    from app.services.parser_health_service import sanitize_error

    raw = "Connection error: postgresql://user:secret@host/db"
    cleaned = sanitize_error(raw)
    assert "secret" not in cleaned
    assert "[REDACTED]" in cleaned

    raw2 = "api_key=my_super_secret_token_xyz"
    cleaned2 = sanitize_error(raw2)
    assert "my_super_secret_token_xyz" not in cleaned2
    assert "[REDACTED]" in cleaned2


@pytest.mark.asyncio
async def test_parser_health_endpoint(client):
    response = await client.get("/api/parser/health")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
