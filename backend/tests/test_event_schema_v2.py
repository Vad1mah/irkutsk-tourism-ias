"""Тесты расширенной схемы Event (фаза 1 B2B-rebuild)."""
from datetime import date, time
import pytest

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
