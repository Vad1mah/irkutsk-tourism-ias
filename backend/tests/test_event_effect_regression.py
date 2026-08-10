"""Тесты регрессионной оценки событийного эффекта.

Проверяется главное свойство оценки: она обязана находить эффект, который в
данные заложен, и не находить эффект, которого там нет. Синтетические ряды
строятся с той же структурой, что реальная панель — сезонность, день недели,
разброс по районам, — чтобы контрольные столбцы модели работали не вхолостую.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from app.services.methodology_service import methodology_service

DISTRICTS = ["Иркутский", "Ольхонский", "Слюдянский"]
START = date(2025, 1, 6)
DAYS = 500
# sigma дневного шума близка к наблюдаемой на проде (~6-7 п.п.).
NOISE_SIGMA = 6.0


def _make_panel(
    effect_pp: float,
    event_dates: dict[str, set[date]],
    *,
    seed: int = 7,
    skip: set[date] | None = None,
) -> list[tuple[str, date, float]]:
    """Синтетическая панель район×день с сезонностью, недельным профилем и шумом."""
    import numpy as np

    rng = np.random.default_rng(seed)
    skip = skip or set()
    rows: list[tuple[str, date, float]] = []
    for d_i, district in enumerate(DISTRICTS):
        level = 55.0 + 6.0 * d_i
        for offset in range(DAYS):
            day = START + timedelta(days=offset)
            if day in skip:
                continue
            doy = day.timetuple().tm_yday
            seasonal = 12.0 * math.sin(2 * math.pi * doy / 365.25)
            weekend = 8.0 if day.weekday() >= 4 else 0.0
            bump = effect_pp if day in event_dates.get(district, set()) else 0.0
            occ = level + seasonal + weekend + bump + float(rng.normal(0, NOISE_SIGMA))
            rows.append((district, day, occ))
    return rows


def _weekend_events(every: int = 3) -> dict[str, set[date]]:
    """События преимущественно по выходным — как в реальных данных."""
    out: dict[str, set[date]] = {}
    for district in DISTRICTS:
        days: set[date] = set()
        for offset in range(DAYS):
            day = START + timedelta(days=offset)
            if day.weekday() >= 4 and offset % every == 0:
                days.add(day)
        out[district] = days
    return out


def test_recovers_planted_effect():
    """Заложенный эффект +8 п.п. должен попасть внутрь доверительного интервала."""
    events = _weekend_events()
    panel = _make_panel(8.0, events)

    result = methodology_service.event_effect_regression(
        panel=panel, event_days=events, placebo_rounds=200
    )

    assert result is not None
    assert result.ci_lower <= 8.0 <= result.ci_upper, (
        f"истинные +8 п.п. вне интервала [{result.ci_lower}, {result.ci_upper}]"
    )
    assert result.ci_lower > 0, "эффект такой силы обязан отличаться от нуля"
    assert result.placebo_p is not None and result.placebo_p < 0.05
    assert result.n_districts == len(DISTRICTS)
    assert result.n_event_days == sum(len(v) for v in events.values())


def test_null_effect_is_calibrated():
    """Без заложенного эффекта ложные срабатывания держатся у номинальных 5%.

    Проверять один seed бессмысленно: 95%-интервал по построению промахивается
    примерно в 5% случаев, и подбор «удачного» seed'а превратил бы тест в
    подгонку. Меряется частота промахов по независимым выборкам — это заодно
    калибровка самой процедуры, а не только её работоспособность.
    """
    events = _weekend_events()
    seeds = range(100, 140)

    misses = 0
    taus: list[float] = []
    for seed in seeds:
        panel = _make_panel(0.0, events, seed=seed)
        result = methodology_service.event_effect_regression(
            panel=panel, event_days=events, placebo_rounds=0
        )
        assert result is not None
        taus.append(result.tau)
        if result.ci_lower > 0.0 or result.ci_upper < 0.0:
            misses += 1

    n = len(list(seeds))
    assert misses <= 6, f"ложных срабатываний {misses} из {n} при номинале ~5%"
    assert abs(sum(taus) / n) < 1.0, f"систематический сдвиг оценки: {sum(taus)/n:.2f} п.п."


def test_placebo_is_calibrated_under_null():
    """Плацебо-тест под нулевой гипотезой не должен часто давать p < 0.05."""
    events = _weekend_events()
    significant = 0
    seeds = range(200, 220)

    for seed in seeds:
        panel = _make_panel(0.0, events, seed=seed)
        result = methodology_service.event_effect_regression(
            panel=panel, event_days=events, placebo_rounds=300
        )
        assert result is not None and result.placebo_p is not None
        if result.placebo_p < 0.05:
            significant += 1

    assert significant <= 4, f"плацебо срабатывает {significant} раз из {len(list(seeds))}"


def test_survives_data_gap():
    """Длинный провал данных не ломает оценку — строки просто отсутствуют."""
    gap = {START + timedelta(days=o) for o in range(120, 243)}
    events = _weekend_events()
    panel = _make_panel(8.0, events, seed=3, skip=gap)

    result = methodology_service.event_effect_regression(
        panel=panel, event_days=events, placebo_rounds=100
    )

    assert result is not None
    assert result.n_obs == len(panel)
    assert result.ci_lower <= 8.0 <= result.ci_upper


def test_returns_none_without_events():
    """Нечего оценивать: ни одного событийного дня."""
    panel = _make_panel(0.0, {})
    assert methodology_service.event_effect_regression(panel=panel, event_days={}) is None


def test_returns_none_on_empty_panel():
    assert methodology_service.event_effect_regression(panel=[], event_days={}) is None


def test_drops_districts_below_threshold():
    """Район с горсткой наблюдений не должен попадать в оценку."""
    events = _weekend_events()
    panel = _make_panel(8.0, events)
    thin_day = START + timedelta(days=1)
    panel.append(("Мамско-Чуйский", thin_day, 40.0))

    result = methodology_service.event_effect_regression(
        panel=panel, event_days=events, placebo_rounds=0, min_days_per_district=30
    )

    assert result is not None
    assert result.n_districts == len(DISTRICTS)
    assert result.min_days_per_district == 30
    assert result.placebo_p is None


def test_seasonal_peak_is_not_mistaken_for_effect():
    """События, совпавшие с сезонным пиком района, не должны дать ложный эффект.

    Воспроизводит ситуацию Ольхонского района на реальных данных: своя резкая
    сезонность (ледовый сезон в феврале — загрузка 76% против 28% в октябре) и
    все событийные дни внутри этого пика. При общей на регион сезонной кривой
    из гармоник дня года такая конфигурация давала +15 п.п. на пустом месте.
    """
    import numpy as np

    # Помесячные уровни повторяют наблюдаемые: Иркутский ровный, Ольхонский резкий.
    levels = {
        "Иркутский": [51, 70, 64, 56, 56, 64, 66, 69, 62, 60, 53, 51],
        "Ольхонский": [48, 76, 57, 52, 41, 40, 62, 68, 40, 28, 28, 33],
    }
    rng = np.random.default_rng(42)
    events: dict[str, set[date]] = {"Иркутский": set(), "Ольхонский": set()}
    panel: list[tuple[str, date, float]] = []

    for district, monthly in levels.items():
        for offset in range(DAYS):
            day = START + timedelta(days=offset)
            weekend = 6.0 if day.weekday() >= 4 else 0.0
            occ = monthly[day.month - 1] + weekend + float(rng.normal(0, 5.0))
            panel.append((district, day, occ))
            if district == "Ольхонский" and day.month in (2, 3) and day.weekday() >= 4:
                events[district].add(day)
            elif district == "Иркутский" and offset % 9 == 0:
                events[district].add(day)

    result = methodology_service.event_effect_regression(
        panel=panel, event_days=events, placebo_rounds=400
    )

    assert result is not None
    assert result.ci_lower <= 0.0 <= result.ci_upper, (
        f"сезонный пик принят за эффект: {result.tau:+.2f} "
        f"[{result.ci_lower:+.2f}, {result.ci_upper:+.2f}]"
    )
    assert result.placebo_p is not None and result.placebo_p > 0.05


@pytest.mark.parametrize("planted", [-6.0, 12.0])
def test_sign_and_magnitude_track_input(planted: float):
    """Оценка следует за знаком и величиной заложенного эффекта."""
    events = _weekend_events(every=2)
    panel = _make_panel(planted, events, seed=int(abs(planted)) + 1)

    result = methodology_service.event_effect_regression(
        panel=panel, event_days=events, placebo_rounds=0
    )

    assert result is not None
    assert result.ci_lower <= planted <= result.ci_upper
