"""Расчёт baseline и corrected impact для событий.

Методология (см. spec §6.3):
- baseline = среднее occupancy на похожих днях недели в окне ±N недель,
  исключая дни других событий и gap-периоды.
- corrected_impact = (observed - baseline) / baseline * 100%
- confidence = функция от размера выборки.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Literal


@dataclass(frozen=True)
class SeasonalBaseline:
    mean: float | None
    std: float | None
    n_samples: int
    confidence: Literal["high", "medium", "low"]


class MethodologyService:
    """Stateless: все методы pure-функции. Удобен для тестов и DI."""

    def compute_seasonal_baseline(
        self,
        *,
        target_date: date,
        target_weekday: int,
        occupancy_history: Iterable[tuple[date, float]],
        event_dates: set[date],
        window_weeks: int = 3,
    ) -> SeasonalBaseline:
        from statistics import mean, stdev

        cutoff_min = target_date - timedelta(weeks=window_weeks)
        cutoff_max = target_date + timedelta(weeks=window_weeks)

        samples = [
            occ
            for d, occ in occupancy_history
            if cutoff_min <= d <= cutoff_max
            and d != target_date
            and d.weekday() == target_weekday
            and d not in event_dates
            and occ is not None
        ]

        n = len(samples)
        if n == 0:
            return SeasonalBaseline(mean=None, std=None, n_samples=0, confidence="low")

        m = float(mean(samples))
        s = float(stdev(samples)) if n >= 2 else 0.0
        confidence: Literal["high", "medium", "low"] = (
            "high" if n >= 5 else "medium" if n >= 3 else "low"
        )
        return SeasonalBaseline(mean=m, std=s, n_samples=n, confidence=confidence)

    def corrected_impact(
        self,
        *,
        observed: float,
        baseline: SeasonalBaseline,
    ) -> dict:
        if baseline.mean is None or baseline.mean == 0:
            return {"delta_pct": None, "confidence": baseline.confidence}
        delta = (observed - baseline.mean) / baseline.mean * 100.0
        # 95% CI (упрощённо: ±1.96 * std/sqrt(n) в %)
        if baseline.std is not None and baseline.n_samples >= 2:
            from math import sqrt
            ci_half = 1.96 * baseline.std / sqrt(baseline.n_samples)
            ci_pct = ci_half / baseline.mean * 100.0
        else:
            ci_pct = None
        return {
            "delta_pct": round(delta, 2),
            "ci_lower": round(delta - ci_pct, 2) if ci_pct else None,
            "ci_upper": round(delta + ci_pct, 2) if ci_pct else None,
            "baseline_mean": round(baseline.mean, 2),
            "n_samples": baseline.n_samples,
            "confidence": baseline.confidence,
            "method": "seasonal_corrected",
        }


methodology_service = MethodologyService()
