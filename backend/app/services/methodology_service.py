"""Расчёт baseline и corrected impact для событий.

Методология (см. spec §6.3):
- baseline = среднее occupancy на похожих днях недели в окне ±N недель,
  исключая дни других событий и gap-периоды.
- corrected_impact = (observed - baseline) / baseline * 100%
- confidence = функция от размера выборки.

Также экспортируется `METHODOLOGY_PROMPT_RULES` — единый источник 8 правил
для системных промптов AI-агента (см. main_agent + llm_service RAG-fallback).
Изменять только здесь — оба промпта импортируют эту строку.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import sqrt
from statistics import mean, stdev
from typing import Iterable, Literal

from scipy.stats import t as student_t

from app.constants import BASELINE_CONFIDENCE_HIGH, BASELINE_CONFIDENCE_MEDIUM


METHODOLOGY_PROMPT_RULES = """1. Всегда указывай район или географический скоп ответа.
2. Всегда указывай период данных, на которые опирается ответ.
3. Всегда указывай метод/методологию метрики (например, "seasonal_corrected" для impact событий).
4. Всегда указывай базу для сравнения (с прошлой неделей, с регионом, с baseline).
5. При нехватке данных — явно говори, чего не хватает, не выдумывай.
6. Не сравнивай отель с конкретными конкурентами — у нас нет данных; используй сегментный benchmark.
7. RevPAR и ADR — это прокси (рассчитываются из min_price), а не реальные значения; помечай это.
8. Период gap данных июль-сентябрь 2025 известен; не интерполируй молча — явно отмечай разрыв."""


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
            "high" if n >= BASELINE_CONFIDENCE_HIGH else
            "medium" if n >= BASELINE_CONFIDENCE_MEDIUM else
            "low"
        )
        return SeasonalBaseline(mean=m, std=s, n_samples=n, confidence=confidence)

    def corrected_impact(
        self,
        *,
        observed: float,
        baseline: SeasonalBaseline,
    ) -> dict:
        if baseline.mean is None or baseline.mean == 0:
            return {
                "delta_pct": None,
                "confidence": baseline.confidence,
                "n_samples": baseline.n_samples,
                "method": "naive_fallback",
            }
        delta = (observed - baseline.mean) / baseline.mean * 100.0
        # Интервал строится вокруг разности «одно наблюдение минус среднее по
        # похожим дням», поэтому в него входят обе составляющие разброса:
        # погрешность самого среднего (sigma/sqrt(n)) и собственный разброс
        # единичного наблюдения (sigma). Отсюда множитель sqrt(1 + 1/n).
        # Квантиль берётся из t-распределения: n здесь обычно 2-6, и нормальный
        # множитель 1.96 на таких выборках даёт заведомо узкий интервал.
        # Замер покрытия на безсобытийных днях (истинный impact = 0):
        # прежняя формула 1.96*sigma/sqrt(n) — 63.5% при номинале 95%,
        # текущая — 98.9%. Скрипт: scripts/check_impact_ci_calibration.py.
        n = baseline.n_samples
        if baseline.std is not None and n >= 2:
            t_crit = float(student_t.ppf(0.975, n - 1))
            ci_half = t_crit * baseline.std * sqrt(1.0 + 1.0 / n)
            ci_pct = ci_half / baseline.mean * 100.0
        else:
            ci_pct = None
        return {
            "delta_pct": round(delta, 2),
            "ci_lower": round(delta - ci_pct, 2) if ci_pct is not None else None,
            "ci_upper": round(delta + ci_pct, 2) if ci_pct is not None else None,
            "baseline_mean": round(baseline.mean, 2),
            "n_samples": baseline.n_samples,
            "confidence": baseline.confidence,
            "method": "seasonal_corrected",
        }


methodology_service = MethodologyService()
