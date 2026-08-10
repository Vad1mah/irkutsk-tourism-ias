"""Проверка калибровки доверительного интервала событийного impact.

Метод. Для дня БЕЗ события истинный impact равен нулю. Значит у корректно
откалиброванного 95%-интервала ноль должен попадать внутрь примерно в 95%
случаев. Скрипт прогоняет `methodology_service` по всем безсобытийным дням
истории и печатает фактическое покрытие — отдельно для текущей формулы и для
варианта с t-квантилем и множителем sqrt(1 + 1/n).

Почему это не придирка: интервал строится вокруг разности «наблюдение минус
среднее по похожим дням». Погрешность среднего (sigma/sqrt(n)) — только одна из
двух составляющих; вторая — собственный разброс одного наблюдения (sigma).

Запуск (из backend/, venv активирован):
    python scripts/check_impact_ci_calibration.py --occ ../occ_irk.csv --events ../event_dates.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime
from math import sqrt
from pathlib import Path
from statistics import mean, stdev

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scipy import stats  # noqa: E402

# Дефолт окна baseline берётся из /api/analytics/events-impact (window_weeks=3).
DEFAULT_WINDOW_WEEKS = 3


def load_occupancy(path: Path) -> list[tuple[date, float]]:
    """Прочитать ряд занятости из CSV `date,occupancy`."""
    rows: list[tuple[date, float]] = []
    with path.open(encoding="utf-8") as fh:
        for parts in csv.reader(fh):
            if len(parts) < 2:
                continue
            try:
                rows.append((datetime.strptime(parts[0].strip(), "%Y-%m-%d").date(),
                             float(parts[1])))
            except ValueError:
                continue
    return sorted(rows)


def load_dates(path: Path) -> set[date]:
    """Прочитать множество дат событий (по одной в строке)."""
    out: set[date] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.add(datetime.strptime(line, "%Y-%m-%d").date())
        except ValueError:
            continue
    return out


def _samples_for(target: date, history: list[tuple[date, float]],
                 event_dates: set[date], window_weeks: int) -> list[float]:
    """Похожие дни: тот же день недели, окно +-N недель, без событий и без самого дня."""
    lo = target.fromordinal(target.toordinal() - window_weeks * 7)
    hi = target.fromordinal(target.toordinal() + window_weeks * 7)
    return [
        occ for d, occ in history
        if lo <= d <= hi and d != target
        and d.weekday() == target.weekday() and d not in event_dates
    ]


def evaluate(history: list[tuple[date, float]], event_dates: set[date],
             window_weeks: int) -> dict:
    """Посчитать фактическое покрытие нуля для обеих формул интервала."""
    stats_by_n: dict[int, dict] = {}
    current_hits = corrected_hits = total = 0

    for target, observed in history:
        if target in event_dates:
            continue
        samples = _samples_for(target, history, event_dates, window_weeks)
        n = len(samples)
        if n < 2:
            continue
        m = mean(samples)
        if m == 0:
            continue
        s = stdev(samples)
        delta = (observed - m) / m * 100.0

        # Текущая формула: 1.96 * sigma/sqrt(n)
        cur_half = 1.96 * s / sqrt(n) / m * 100.0
        # Корректная: t(0.975, n-1) * sigma * sqrt(1 + 1/n)
        corr_half = float(stats.t.ppf(0.975, n - 1)) * s * sqrt(1 + 1 / n) / m * 100.0

        cur_ok = abs(delta) <= cur_half
        corr_ok = abs(delta) <= corr_half
        current_hits += cur_ok
        corrected_hits += corr_ok
        total += 1

        bucket = stats_by_n.setdefault(n, {"n_days": 0, "cur": 0, "corr": 0})
        bucket["n_days"] += 1
        bucket["cur"] += cur_ok
        bucket["corr"] += corr_ok

    return {"total": total, "current": current_hits,
            "corrected": corrected_hits, "by_n": stats_by_n}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--occ", required=True, type=Path)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--window-weeks", type=int, default=DEFAULT_WINDOW_WEEKS)
    args = parser.parse_args()

    history = load_occupancy(args.occ)
    event_dates = load_dates(args.events)
    print(f"История: {len(history)} дней, дат с событиями: {len(event_dates)}, "
          f"окно +-{args.window_weeks} нед.")

    res = evaluate(history, event_dates, args.window_weeks)
    if not res["total"]:
        print("Недостаточно данных для оценки покрытия")
        return

    total = res["total"]
    print(f"\nБезсобытийных дней с n>=2 похожими днями: {total}")
    print("Целевое покрытие 95% (ноль внутри интервала)\n")
    print(f"{'формула':>34} | {'покрытие':>9} | {'попаданий':>9}")
    print(f"{'текущая: 1.96*s/sqrt(n)':>34} | "
          f"{res['current'] / total * 100:>8.1f}% | {res['current']:>4}/{total}")
    print(f"{'исправленная: t*s*sqrt(1+1/n)':>34} | "
          f"{res['corrected'] / total * 100:>8.1f}% | {res['corrected']:>4}/{total}")

    print(f"\n{'n похожих дней':>15} | {'дней':>5} | {'текущая':>8} | {'исправленная':>12}")
    for n in sorted(res["by_n"]):
        b = res["by_n"][n]
        print(f"{n:>15} | {b['n_days']:>5} | {b['cur'] / b['n_days'] * 100:>7.1f}% | "
              f"{b['corr'] / b['n_days'] * 100:>11.1f}%")


if __name__ == "__main__":
    main()
