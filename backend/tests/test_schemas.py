"""Тесты для Pydantic-схем и db_service."""
import pytest
from datetime import date
from pydantic import ValidationError

from app.models.schemas import (
    Hotel, HotelStatistics, Event,
    ForecastRequest, QueryRequest,
)


class TestHotelSchema:

    def test_valid_hotel(self):
        h = Hotel(
            id="h1", name="Test Hotel", city="Иркутск",
            district="Иркутский", rating=4.5,
        )
        assert h.id == "h1"
        assert h.district == "Иркутский"

    def test_hotel_rating_auto_scale(self):
        """Рейтинг >5 масштабируется /2."""
        h = Hotel(id="h2", name="Hotel", city="City", rating=8.4)
        assert h.rating == 4.2

    def test_hotel_rating_none_allowed(self):
        h = Hotel(id="h3", name="Hotel", city="City", rating=None)
        assert h.rating is None

    def test_hotel_min_price_optional(self):
        h = Hotel(id="h4", name="Hotel", city="City")
        assert h.min_price is None

    def test_hotel_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            Hotel(id="h5", name="", city="City")


class TestHotelStatisticsSchema:

    def test_valid_stats(self):
        s = HotelStatistics(
            id="h1", date=date(2026, 1, 15),
            rooms_num=50, free_rooms_amount=10,
            available_rooms_percent=20.0,
        )
        assert s.available_rooms_percent == 20.0

    def test_negative_rooms_rejected(self):
        with pytest.raises(ValidationError):
            HotelStatistics(
                id="h1", date=date(2026, 1, 1),
                rooms_num=-5,
            )


class TestEventSchema:

    def test_valid_event(self):
        e = Event(
            event_id="e1", title="Фестиваль",
            source_id="irk",
            date_start=date(2026, 7, 1),
        )
        assert e.source_id == "irk"

    def test_event_missing_title_rejected(self):
        with pytest.raises(ValidationError):
            Event(event_id="e2", title="", source_id="irk", date_start=date(2026, 1, 1))

    def test_event_requires_date_start(self):
        with pytest.raises(ValidationError):
            Event(event_id="e3", title="Test", source_id="irk")


class TestForecastRequest:

    def test_default_days(self):
        from app.constants import MAX_FORECAST_HORIZON_DAYS

        r = ForecastRequest(district="Иркутский")
        assert r.days_ahead == MAX_FORECAST_HORIZON_DAYS

    def test_district_optional(self):
        r = ForecastRequest()
        assert r.district is None


class TestQueryRequest:

    def test_valid_query(self):
        q = QueryRequest(text="Какая загрузка?")
        assert q.text == "Какая загрузка?"

    def test_empty_query_rejected(self):
        with pytest.raises(ValidationError):
            QueryRequest(text="")

    def test_too_long_query_rejected(self):
        with pytest.raises(ValidationError):
            QueryRequest(text="x" * 2001)
