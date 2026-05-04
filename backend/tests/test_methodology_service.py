"""Unit-тесты MethodologyService."""
from datetime import date

import pytest

from app.services.methodology_service import (
    MethodologyService,
    SeasonalBaseline,
)


def test_seasonal_baseline_excludes_event_days():
    """Baseline считается только из дней без событий."""
    occupancy_series = [
        (date(2026, 5, 4), 50.0),  # пн
        (date(2026, 5, 11), 55.0),  # пн (день события)
        (date(2026, 5, 18), 48.0),  # пн
        (date(2026, 5, 25), 52.0),  # пн
    ]
    event_dates = {date(2026, 5, 11)}
    svc = MethodologyService()
    baseline = svc.compute_seasonal_baseline(
        target_date=date(2026, 5, 11),
        target_weekday=0,  # пн
        occupancy_history=occupancy_series,
        event_dates=event_dates,
        window_weeks=3,
    )
    # ожидаем среднее 50, 48, 52 = 50.0
    assert isinstance(baseline, SeasonalBaseline)
    assert abs(baseline.mean - 50.0) < 0.5
    assert baseline.n_samples == 3


def test_seasonal_baseline_returns_low_confidence_on_few_samples():
    """При <3 точек выборки confidence='low' и mean=None."""
    svc = MethodologyService()
    baseline = svc.compute_seasonal_baseline(
        target_date=date(2026, 5, 11),
        target_weekday=0,
        occupancy_history=[(date(2026, 5, 4), 50.0)],
        event_dates=set(),
        window_weeks=3,
    )
    assert baseline.confidence == "low"
    assert baseline.n_samples == 1
