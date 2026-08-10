"""Фоллбэк агентских tools на PostgreSQL при пустом векторном индексе.

ChromaDB на проде не проиндексировал ни одного документа (эмбеддинги GigaChat
отдавали 402, затем 401), из-за чего `search_events` отвечал «данные недоступны»,
хотя вкладка «События» рядом показывала те же события из PostgreSQL. Тесты
фиксируют, что при пустой коллекции инструменты берут данные из БД.
"""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.services import main_agent


class _StubDataService:
    """Минимальная замена data_service: отдаёт заранее заданные строки."""

    def __init__(self, events=None, hotels=None, connected=True):
        self._events = events or []
        self._hotels = hotels or []
        self.is_connected = connected
        self.hotels_calls: list[dict] = []

    async def get_events(self, date_from=None, limit=200, **kwargs):
        return self._events

    async def get_hotels(self, city=None, district=None, limit=100, **kwargs):
        self.hotels_calls.append({"city": city, "district": district})
        if city and city != "Листвянка":
            return [], 0
        return self._hotels, len(self._hotels)


def _event(title: str, event_type: str = "concert", days: int = 3) -> dict:
    return {
        "title": title,
        "event_type": event_type,
        "location": "Иркутск",
        "date_start": date.today() + timedelta(days=days),
    }


def _hotel(name: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name, city="Листвянка", accommodation_type="Отель", min_price=4200,
    )


@pytest.mark.asyncio
async def test_events_fallback_returns_db_rows(monkeypatch):
    stub = _StubDataService(events=[_event("Джазовый концерт"), _event("Ледовый фестиваль")])
    monkeypatch.setattr("app.services.data_service.data_service", stub, raising=False)

    result = await main_agent._search_events_in_db("концерт")

    assert "Джазовый концерт" in result
    assert "недоступн" not in result.lower()


@pytest.mark.asyncio
async def test_events_fallback_keeps_all_when_query_matches_nothing(monkeypatch):
    """Пустой результат фильтра не должен превращаться в «ничего не найдено»."""
    stub = _StubDataService(events=[_event("Ледовый фестиваль", "festival")])
    monkeypatch.setattr("app.services.data_service.data_service", stub, raising=False)

    result = await main_agent._search_events_in_db("баскетбол")

    assert "Ледовый фестиваль" in result


@pytest.mark.asyncio
async def test_events_fallback_filters_by_month(monkeypatch):
    far = date.today() + timedelta(days=200)
    stub = _StubDataService(events=[
        {"title": "Дальнее событие", "event_type": "concert",
         "location": "Иркутск", "date_start": far},
    ])
    monkeypatch.setattr("app.services.data_service.data_service", stub, raising=False)

    other_month = 1 if far.month != 1 else 2
    result = await main_agent._search_events_in_db("концерт", month=other_month)

    assert "Дальнее событие" not in result


@pytest.mark.asyncio
async def test_events_fallback_reports_db_down(monkeypatch):
    monkeypatch.setattr(
        "app.services.data_service.data_service",
        _StubDataService(connected=False),
        raising=False,
    )

    result = await main_agent._search_events_in_db("концерт")

    assert "недоступна" in result


@pytest.mark.asyncio
async def test_hotels_fallback_returns_db_rows(monkeypatch):
    stub = _StubDataService(hotels=[_hotel("Байкал Резорт")])
    monkeypatch.setattr("app.services.data_service.data_service", stub, raising=False)

    result = await main_agent._search_hotels_in_db("Листвянка")

    assert "Байкал Резорт" in result
    assert "4200" in result


@pytest.mark.asyncio
async def test_hotels_fallback_retries_by_district(monkeypatch):
    """Если по городу пусто — пробуем район, а не сдаёмся сразу."""
    stub = _StubDataService(hotels=[_hotel("Ольхон Хостел")])
    monkeypatch.setattr("app.services.data_service.data_service", stub, raising=False)

    await main_agent._search_hotels_in_db("Хужир")

    assert stub.hotels_calls[0]["city"] == "Хужир"
    assert any(call["district"] for call in stub.hotels_calls[1:])
