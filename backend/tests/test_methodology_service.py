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
    """При <3 точек выборки confidence='low'."""
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


def test_seasonal_baseline_returns_none_mean_on_empty_history():
    """Пустая выборка → mean=None, n_samples=0, confidence='low'."""
    svc = MethodologyService()
    baseline = svc.compute_seasonal_baseline(
        target_date=date(2026, 5, 11),
        target_weekday=0,
        occupancy_history=[],
        event_dates=set(),
        window_weeks=3,
    )
    assert baseline.mean is None
    assert baseline.n_samples == 0
    assert baseline.confidence == "low"


def test_corrected_impact_with_zero_std_yields_zero_width_ci():
    """std=0 (все samples одинаковы) → ci_lower==ci_upper (не None)."""
    svc = MethodologyService()
    baseline = SeasonalBaseline(mean=50.0, std=0.0, n_samples=5, confidence="high")
    result = svc.corrected_impact(observed=55.0, baseline=baseline)
    assert result["delta_pct"] == 10.0
    assert result["ci_lower"] is not None
    assert result["ci_upper"] is not None
    assert result["ci_lower"] == result["ci_upper"] == 10.0


def test_corrected_impact_baseline_zero_returns_none_delta():
    """baseline.mean=0 → delta_pct=None (нет div-by-zero)."""
    svc = MethodologyService()
    baseline = SeasonalBaseline(mean=0.0, std=0.0, n_samples=5, confidence="high")
    result = svc.corrected_impact(observed=50.0, baseline=baseline)
    assert result["delta_pct"] is None
