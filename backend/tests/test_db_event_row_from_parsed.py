"""Регрессионный тест: _build_event_row должен принимать ParsedEvent, а не только dict.

Баг: scheduler.collect_events передаёт list[ParsedEvent] в upsert_events_batch,
который вызывает _build_event_row(ev) с ev.get(...). У Pydantic-модели ParsedEvent
нет метода .get() → AttributeError возникает в цикле ДО try/except вокруг DB →
upsert падает целиком → 0 событий сохраняется на каждом прогоне scheduler'а.
"""
from datetime import date

from app.parsers.base import ParsedEvent
from app.services.db_service import DBService


def test_build_event_row_accepts_parsed_event():
    """ParsedEvent (Pydantic) должен корректно маппиться в row для upsert."""
    svc = DBService()
    ev = ParsedEvent(
        id="irk_abc123def456",
        title="День города на улице Урицкого",
        description=None,
        date_start="2026-06-06",
        event_type="festival",
        location="Иркутск",
        source="irk",
        time_start="18:00",
        price_min=500,
        url="https://irk.ru/afisha/x",
    )

    row = svc._build_event_row(ev)

    assert row is not None
    assert row["event_id"] == "irk_abc123def456"
    assert row["title"] == "День города на улице Урицкого"
    assert row["date_start"] == date(2026, 6, 6)
    assert row["source_id"] == "irk"
    assert row["price_min"] == 500


def test_build_event_row_still_accepts_dict():
    """Регрессия: dict-вход (путь /api/parser/events/{src}) продолжает работать."""
    svc = DBService()
    row = svc._build_event_row({
        "id": "zeroevent_1",
        "title": "Концерт",
        "date_start": "2026-07-01",
        "source": "zeroevent",
    })

    assert row is not None
    assert row["event_id"] == "zeroevent_1"
    assert row["source_id"] == "zeroevent"
    assert row["date_start"] == date(2026, 7, 1)
