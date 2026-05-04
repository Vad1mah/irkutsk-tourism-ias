"""Тесты расширенной схемы Event (фаза 1 B2B-rebuild)."""
import pytest
from datetime import date, time

from app.db.models import Event


def test_event_orm_has_new_fields():
    """ORM-модель Event должна иметь 6 новых полей."""
    columns = {c.name for c in Event.__table__.columns}
    expected_new = {
        "time_start",
        "price_min",
        "price_max",
        "image_url",
        "address",
        "age_restriction",
    }
    assert expected_new.issubset(columns), f"Missing: {expected_new - columns}"


def test_event_orm_can_instantiate_with_new_fields():
    """ORM-объект Event можно сконструировать со всеми новыми полями."""
    e = Event(
        event_id="test-1",
        title="Test event",
        date_start=date(2026, 5, 10),
        source_id="test",
        time_start=time(19, 30),
        price_min=500,
        price_max=2500,
        image_url="https://example.com/img.jpg",
        address="ул. Ленина, 1, Иркутск",
        age_restriction="16+",
    )
    assert e.time_start.hour == 19
    assert e.price_min == 500
    assert e.age_restriction == "16+"


def test_event_pydantic_accepts_new_fields():
    """Pydantic-схема Event принимает новые поля и валидирует их."""
    from app.models.schemas import Event as EventSchema

    payload = {
        "event_id": "abc-1",
        "title": "Концерт",
        "date_start": "2026-06-01",
        "source_id": "yandex",
        "time_start": "19:30:00",
        "price_min": 1000,
        "price_max": 3500,
        "image_url": "https://example.com/poster.jpg",
        "address": "ул. Ленина, 5",
        "age_restriction": "12+",
    }
    e = EventSchema(**payload)
    assert e.time_start.hour == 19
    assert e.price_min == 1000
    assert e.price_max == 3500
    assert e.image_url == "https://example.com/poster.jpg"
    assert e.address == "ул. Ленина, 5"
    assert e.age_restriction == "12+"


def test_event_pydantic_optional_new_fields():
    """Все 6 новых полей опциональны (можно создать без них)."""
    from app.models.schemas import Event as EventSchema

    e = EventSchema(
        event_id="abc-2",
        title="Минимальное событие",
        date_start="2026-06-02",
        source_id="manual",
    )
    assert e.time_start is None
    assert e.price_min is None
    assert e.price_max is None
    assert e.image_url is None
    assert e.address is None
    assert e.age_restriction is None


@pytest.mark.asyncio(loop_scope="session")
async def test_event_dedup_on_conflict(setup_services):
    """Двойная вставка одного события не создаёт дубль."""
    from app.services.db_service import db_service
    from app.services.data_service import data_service

    if not data_service.is_connected:
        pytest.skip("DB not available")

    payload = {
        "event_id": "test-dedup-1",
        "title": "Тестовое событие dedup",
        "date_start": date(2099, 1, 1),
        "source_id": "test_dedup",
        "event_type": "Test",
    }

    # Первая вставка
    await db_service.upsert_event(**payload)
    # Вторая — с другим event_id, но тем же (source_id, date_start, title)
    payload2 = {**payload, "event_id": "test-dedup-2"}
    await db_service.upsert_event(**payload2)

    # Проверить, что в БД ровно одна строка
    rows = await data_service.get_events(
        date_from=date(2099, 1, 1),
        date_to=date(2099, 1, 1),
    )
    matching = [r for r in rows if r.get("title") == payload["title"]]
    assert len(matching) == 1, f"Expected 1 row, got {len(matching)}"

    # Cleanup
    await db_service.delete_event_by_id("test-dedup-1")
    await db_service.delete_event_by_id("test-dedup-2")


@pytest.mark.asyncio(loop_scope="session")
async def test_event_dedup_preserves_existing_description(setup_services):
    """COALESCE: повторная вставка с description=None не стирает существующее описание."""
    from app.services.db_service import db_service
    from app.services.data_service import data_service

    if not data_service.is_connected:
        pytest.skip("DB not available")

    payload = {
        "event_id": "test-coalesce-1",
        "title": "Тест COALESCE",
        "date_start": date(2099, 1, 2),
        "source_id": "test_coalesce",
        "description": "First description",
    }
    await db_service.upsert_event(**payload)

    # Вторая вставка с description=None — существующее описание должно сохраниться
    payload2 = {**payload, "event_id": "test-coalesce-2", "description": None}
    await db_service.upsert_event(**payload2)

    rows = await data_service.get_events(
        date_from=date(2099, 1, 2),
        date_to=date(2099, 1, 2),
    )
    matching = [r for r in rows if r.get("title") == "Тест COALESCE"]
    assert len(matching) == 1
    assert matching[0].get("description") == "First description", (
        f"Expected description preserved, got: {matching[0].get('description')}"
    )

    # Cleanup
    await db_service.delete_event_by_id("test-coalesce-1")
    await db_service.delete_event_by_id("test-coalesce-2")


@pytest.mark.asyncio(loop_scope="session")
async def test_parser_all_no_duplicates_on_rerun(setup_services):
    """Повторный запуск /parser/events/all не создаёт дублей."""
    from app.services.data_service import data_service

    if not data_service.is_connected:
        pytest.skip("DB not available")

    rows = await data_service.get_events()
    seen: set[tuple] = set()
    for r in rows:
        key = (r.get("source_id") or r.get("source"), r.get("date_start"), r.get("title"))
        assert key not in seen, f"Duplicate detected: {key}"
        seen.add(key)
