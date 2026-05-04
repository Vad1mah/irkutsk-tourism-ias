"""Протоколы сервисов для типизации DI."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable

from app.models.schemas import ForecastPoint, Hotel as HotelSchema, HotelStatistics


@runtime_checkable
class DataServiceProtocol(Protocol):
    """Общий интерфейс для сервиса данных."""

    @property
    def is_connected(self) -> bool: ...

    async def connect(self) -> None: ...
    async def close(self) -> None: ...

    async def get_hotels(
        self, city: str | None = None, district: str | None = None,
        limit: int = 100, offset: int = 0,
    ) -> tuple[list[HotelSchema], int]: ...

    async def get_hotel_statistics(
        self,
        hotel_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[HotelStatistics]: ...

    async def get_events(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        source: str | None = None,
        city: str | None = None,
    ) -> list[dict]: ...

    async def get_occupancy_by_district(
        self,
        district: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict]: ...

    async def get_monthly_statistics(self, year: int | None = None) -> list[dict]: ...
    async def get_events_by_month(self, year: int | None = None) -> list[dict]: ...
    async def get_districts_statistics(self) -> list[dict]: ...
    async def get_total_metrics(self) -> dict: ...
    async def get_hotels_by_city(self) -> list[dict]: ...
    async def get_hotels_by_district(self) -> list[dict]: ...

    async def insert_event(self, event: dict) -> bool: ...
    async def insert_events_batch(self, events: list[dict]) -> int: ...
    async def upsert_events_batch(self, events: list[dict]) -> int: ...
    async def delete_events_by_source(self, source: str) -> int: ...
    async def save_hotels(self, hotels: list[dict]) -> int: ...
    async def save_statistics(self, stats: list[dict]) -> int: ...
    async def save_ensemble_forecasts(
        self,
        *,
        district: str,
        forecasts: list[dict],
        model_name: str = "ensemble",
    ) -> int: ...

    async def get_saved_forecasts(self, *, district: str, dates: list[date]) -> dict[date, float]: ...

    async def get_hotels_count(self) -> int: ...
    async def get_events_count(self) -> int: ...
    async def get_data_date_range(self) -> dict: ...
    async def detect_gap_periods(self, min_days: int = 7) -> list[dict]: ...
    async def get_last_data_refresh(self) -> datetime | None: ...

    async def compute_proxy_pickup(
        self,
        *,
        district: str,
        days_ahead: int,
        lookback_days: int,
    ) -> list[dict]: ...

    async def collect_min_prices(self, *, district: str, days: int) -> list[int]: ...


@runtime_checkable
class ForecastServiceProtocol(Protocol):
    """Общий интерфейс для Prophet / NeuralProphet / XGBoost."""

    def forecast_occupancy(
        self,
        history: list[dict],
        days_ahead: int = 14,
        weather_data: dict[date, dict] | None = None,
        events_data: list[dict] | None = None,
        **kwargs: Any,
    ) -> list[ForecastPoint]: ...

    async def forecast_occupancy_async(
        self,
        history: list[dict],
        days_ahead: int = 30,
        weather_data: dict[date, dict] | None = None,
        events_data: list[dict] | None = None,
        **kwargs: Any,
    ) -> list[ForecastPoint]: ...
