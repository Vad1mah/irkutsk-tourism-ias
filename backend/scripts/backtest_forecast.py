"""Контролируемый rolling-origin бэктест прогноза загрузки.

Считает ошибку по КАЖДОМУ горизонту отдельно на честной панели наблюдений
и сравнивает с наивными базлайнами. В отличие от `/api/forecast/{district}/validation`,
который читает таблицу `forecasts` (там upsert затирает прогнозы разных горизонтов),
здесь каждый origin обучается заново на срезе истории до этой даты.

Запуск (из backend/, venv активирован):
    python scripts/backtest_forecast.py --csv ../data_irk_occ.csv --horizon 7 --step 5

CSV: district,date,occupancy,n — как отдаёт SELECT из hotel_statistics.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import math
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.disable(logging.INFO)


def load_series(csv_path: Path) -> list[dict]:
    """Прочитать ряд занятости из CSV-выгрузки."""
    rows: list[dict] = []
    with csv_path.open(encoding="utf-8") as fh:
        for parts in csv.reader(fh):
            if len(parts) < 3:
                continue
            try:
                rows.append({
                    "date": datetime.strptime(parts[1], "%Y-%m-%d").date(),
                    "occupancy": float(parts[2]),
                })
            except ValueError:
                continue
    rows.sort(key=lambda r: r["date"])
    return rows


def _metrics(errors: list[float]) -> dict:
    """MAE / RMSE / смещение по списку ошибок (прогноз минус факт)."""
    if not errors:
        return {"n": 0, "mae": None, "rmse": None, "bias": None}
    n = len(errors)
    return {
        "n": n,
        "mae": sum(abs(e) for e in errors) / n,
        "rmse": math.sqrt(sum(e * e for e in errors) / n),
        "bias": sum(errors) / n,
    }


def _paired_bootstrap(model_err: list[float], naive_err: list[float], iters: int = 10000) -> float:
    """Доля бутстрэп-выборок, где наивный базлайн не хуже модели (одностороннее p)."""
    import random

    if len(model_err) != len(naive_err) or not model_err:
        return float("nan")
    diffs = [abs(m) - abs(nv) for m, nv in zip(model_err, naive_err)]
    n = len(diffs)
    rnd = random.Random(20260809)
    worse = 0
    for _ in range(iters):
        sample = [diffs[rnd.randrange(n)] for _ in range(n)]
        if sum(sample) / n >= 0:
            worse += 1
    return worse / iters


async def run_backtest(series: list[dict], horizon: int, step: int, district: str,
                       min_train: int) -> list[dict]:
    """Прогнать rolling-origin бэктест, вернуть сырые наблюдения по каждой паре (origin, h).

    Один проход даёт ошибки сразу для ансамбля и каждой модели по отдельности —
    `forecast_ensemble_async` возвращает их в поле `models`.
    """
    from app.services.ensemble_service import ensemble_service

    by_date = {r["date"]: r["occupancy"] for r in series}
    observations: list[dict] = []

    for i in range(min_train, len(series) - horizon, step):
        train = series[:i + 1]
        origin = train[-1]["date"]
        last_value = train[-1]["occupancy"]
        week_ago = by_date.get(date.fromordinal(origin.toordinal() - 6))

        try:
            result = await ensemble_service.forecast_ensemble_async(
                history=train, days_ahead=horizon, district=district,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  origin {origin}: ошибка ансамбля — {exc}", file=sys.stderr)
            continue

        series_by_model = {"ensemble": result.get("ensemble", [])}
        for name, pts in (result.get("models") or {}).items():
            series_by_model[name] = pts
        if not series_by_model["ensemble"]:
            print(f"  origin {origin}: ансамбль вернул 0 точек", file=sys.stderr)
            continue

        for model_name, points in series_by_model.items():
            for point in points:
                pdate = point.date if hasattr(point, "date") else point["date"]
                pocc = point.occupancy if hasattr(point, "occupancy") else point["occupancy"]
                actual = by_date.get(pdate)
                if actual is None:
                    continue
                h = (pdate - origin).days
                if h < 1 or h > horizon:
                    continue
                observations.append({
                    "origin": origin, "h": h, "model": model_name,
                    "err": pocc - actual,
                    "naive_err": last_value - actual,
                    "snaive_err": (week_ago - actual) if week_ago is not None else None,
                })

        got = {k: len(v) for k, v in series_by_model.items() if v}
        print(f"  origin {origin}: ok {got}", file=sys.stderr)

    return observations


def report(observations: list[dict], label: str, horizon: int) -> None:
    """Таблица ошибок по горизонтам для каждой модели + тест против наивного базлайна."""
    print(f"\n=== {label} ===")
    if not observations:
        print("наблюдений: 0")
        return
    origins = sorted({o["origin"] for o in observations})
    print(f"origins: {len(origins)}  ({origins[0]} … {origins[-1]})")

    for model_name in sorted({o["model"] for o in observations}):
        rows = [o for o in observations if o["model"] == model_name]
        if not rows:
            continue
        print(f"\n-- {model_name} --")
        print(f"{'h':>3} {'n':>4} | {'MAE':>7} {'RMSE':>7} {'bias':>7} | "
              f"{'MAE наив':>9} | {'MAE сез.наив':>12} | {'p(наив не хуже)':>16}")
        for h in range(1, horizon + 1):
            sub = [o for o in rows if o["h"] == h]
            if not sub:
                continue
            m = _metrics([o["err"] for o in sub])
            nv = _metrics([o["naive_err"] for o in sub])
            sn = _metrics([o["snaive_err"] for o in sub if o["snaive_err"] is not None])
            p = _paired_bootstrap([o["err"] for o in sub], [o["naive_err"] for o in sub])
            print(f"{h:>3} {m['n']:>4} | {m['mae']:>7.2f} {m['rmse']:>7.2f} {m['bias']:>7.2f} | "
                  f"{nv['mae']:>9.2f} | "
                  f"{(sn['mae'] if sn['mae'] is not None else float('nan')):>12.2f} | {p:>16.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--district", default="Иркутский")
    parser.add_argument("--horizon", type=int, default=7)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--min-train", type=int, default=200)
    parser.add_argument("--split", type=str, default="2026-07-01",
                        help="Дата разделения режимов: origins до неё и после считаются отдельно")
    args = parser.parse_args()

    series = load_series(args.csv)
    print(f"Ряд: {len(series)} точек, {series[0]['date']} … {series[-1]['date']}")

    split = datetime.strptime(args.split, "%Y-%m-%d").date()
    observations = asyncio.run(
        run_backtest(series, args.horizon, args.step, args.district, args.min_train)
    )

    report(observations, f"{args.district}: весь период", args.horizon)
    report([o for o in observations if o["origin"] < split],
           f"{args.district}: origins ДО {split}", args.horizon)
    report([o for o in observations if o["origin"] >= split],
           f"{args.district}: origins С {split} (текущий сезонный режим)", args.horizon)


if __name__ == "__main__":
    main()
